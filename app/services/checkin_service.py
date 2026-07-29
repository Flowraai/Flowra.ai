"""Orquestração do check-in: risco → persistência → alerta → auditoria.

Fluxo (seções 4 e 6 do planejamento):
  5. IA analisa a resposta estruturada e o conteúdo livre.
  6. Índice de risco do paciente é atualizado.
  7. Médico só recebe alerta quando o risco exige atenção.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alert import Alert
from app.models.checkin import CheckIn
from app.models.enums import AlertUrgency, AuditAction, RiskLevel
from app.models.patient import Patient
from app.risk.engine import PsychiatricRiskEngine
from app.risk.free_text import get_free_text_analyzer
from app.risk.trend import CheckInPoint, assess_trend
from app.schemas.checkin import CheckInCreate
from app.services import audit
from app.services.notifications import dispatch_alert, doctor_notification_contacts


def _build_engine() -> PsychiatricRiskEngine:
    return PsychiatricRiskEngine(free_text_analyzer=get_free_text_analyzer())


async def process_checkin(
    session: AsyncSession, patient: Patient, payload: CheckInCreate
) -> CheckIn:
    engine = _build_engine()
    # O analisador de texto livre pode chamar um LLM (I/O bloqueante); roda numa
    # thread para não bloquear o event loop. As regras determinísticas são leves.
    assessment = await asyncio.to_thread(
        engine.assess, payload.structured_responses, payload.free_text
    )

    checkin = CheckIn(
        patient_id=patient.id,
        protocol_id=patient.active_protocol_id,
        structured_responses=payload.structured_responses,
        free_text=payload.free_text,
        audio_url=payload.audio_url,
        risk_level=assessment.level,
        risk_reasons=assessment.reasons,
        category_risks=assessment.category_risks,
    )
    session.add(checkin)
    await session.flush()  # garante checkin.id para o alerta e a auditoria

    # Risco por tendência: combina o risco pontual (deste check-in) com o padrão
    # dos check-ins recentes, mantendo o MAIOR risco (conservador).
    trend = await _assess_trend(session, patient, checkin, assessment.level)
    combined_level = assessment.level.escalate(trend.level)
    combined_reasons = assessment.reasons + trend.reasons

    # Atualiza o índice de risco atual do paciente (denormalizado p/ o painel).
    patient.current_risk = combined_level
    patient.last_checkin_at = datetime.now(timezone.utc)

    await audit.record(
        session,
        action=AuditAction.CHECKIN_SUBMITTED,
        actor=f"patient:{patient.id}",
        entity_type="checkin",
        entity_id=checkin.id,
    )
    await audit.record(
        session,
        action=AuditAction.RISK_CALCULATED,
        actor="system",
        entity_type="checkin",
        entity_id=checkin.id,
        metadata={
            "checkin_level": assessment.level.value,
            "trend_level": trend.level.value,
            "combined_level": combined_level.value,
            "reasons": combined_reasons,
        },
    )

    # Alerta apenas quando o risco (pontual ou de tendência) exige atenção (🟠/🔴).
    if combined_level.order >= RiskLevel.ORANGE.order:
        urgency = (
            AlertUrgency.IMMEDIATE
            if combined_level is RiskLevel.RED
            else AlertUrgency.ROUTINE
        )
        alert = Alert(
            patient_id=patient.id,
            checkin_id=checkin.id,
            level=combined_level,
            urgency=urgency,
            reason="; ".join(combined_reasons) or "risco elevado no check-in",
            reasons_detail=combined_reasons,
        )
        session.add(alert)
        await session.flush()

        await audit.record(
            session,
            action=AuditAction.ALERT_CREATED,
            actor="system",
            entity_type="alert",
            entity_id=alert.id,
            metadata={"level": alert.level.value, "urgency": urgency.value},
        )

        email, phone = await doctor_notification_contacts(session, patient)
        await dispatch_alert(session, alert=alert, patient=patient, email=email, phone=phone)

    return checkin


async def _assess_trend(
    session: AsyncSession, patient: Patient, current: CheckIn, current_level: RiskLevel
):
    """Monta a janela recente (atual + anteriores) e avalia a tendência."""
    current_point = CheckInPoint(level=current_level, responses=current.structured_responses or {})
    result = await session.execute(
        select(CheckIn)
        .where(CheckIn.patient_id == patient.id, CheckIn.id != current.id)
        .order_by(CheckIn.created_at.desc())
        .limit(max(settings.risk_trend_window - 1, 0))
    )
    previous = [
        CheckInPoint(level=c.risk_level, responses=c.structured_responses or {})
        for c in result.scalars().all()
    ]
    return assess_trend([current_point, *previous])
