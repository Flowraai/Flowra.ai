"""Orquestração do check-in: risco → persistência → alerta → auditoria.

Fluxo (seções 4 e 6 do planejamento):
  5. IA analisa a resposta estruturada e o conteúdo livre.
  6. Índice de risco do paciente é atualizado.
  7. Médico só recebe alerta quando o risco exige atenção.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.checkin import CheckIn
from app.models.doctor import Doctor
from app.models.enums import AlertUrgency, AuditAction, RiskLevel
from app.models.patient import Patient
from app.models.user import User
from app.risk.engine import PsychiatricRiskEngine
from app.risk.free_text import get_free_text_analyzer
from app.schemas.checkin import CheckInCreate
from app.services import audit
from app.services.notifications import dispatch_alert


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

    # Atualiza o índice de risco atual do paciente (denormalizado p/ o painel).
    patient.current_risk = assessment.level
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
        metadata={"level": assessment.level.value, "reasons": assessment.reasons},
    )

    # Alerta apenas quando o risco exige atenção do médico (🟠 ou 🔴).
    if assessment.level.order >= RiskLevel.ORANGE.order:
        urgency = (
            AlertUrgency.IMMEDIATE
            if assessment.level is RiskLevel.RED
            else AlertUrgency.ROUTINE
        )
        alert = Alert(
            patient_id=patient.id,
            checkin_id=checkin.id,
            level=assessment.level,
            urgency=urgency,
            reason="; ".join(assessment.reasons) or "risco elevado no check-in",
            reasons_detail=assessment.reasons,
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

        target = await _doctor_notification_target(session, patient)
        await dispatch_alert(session, alert=alert, patient=patient, target=target)

    return checkin


async def _doctor_notification_target(session: AsyncSession, patient: Patient) -> str:
    """E-mail do médico responsável (destino da notificação); fallback estável."""
    doctor = await session.get(Doctor, patient.doctor_id)
    if doctor is not None:
        user = await session.get(User, doctor.user_id)
        if user is not None and user.email:
            return user.email
    return f"doctor:{patient.doctor_id}"
