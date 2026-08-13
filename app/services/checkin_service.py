"""Orquestração do check-in: risco → persistência → alerta → auditoria.

Fluxo (seções 4 e 6 do planejamento):
  5. IA analisa a resposta estruturada e o conteúdo livre.
  6. Índice de risco do paciente é atualizado.
  7. Médico só recebe alerta quando o risco exige atenção.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alert import Alert
from app.models.checkin import CheckIn
from app.models.enums import AlertUrgency, AuditAction, RiskLevel
from app.models.patient import Patient
from app.risk.engine import PsychiatricRiskEngine
from app.risk.free_text import analyzer_for
from app.risk.trend import CheckInPoint, assess_trend
from app.models.attachment import Attachment
from app.schemas.checkin import CheckInCreate
from app.services import audit
from app.services.attachment_service import attachment_id_from_ref, load_bytes
from app.services.notifications import dispatch_alert, doctor_notification_contacts
from app.services.transcription import transcribe

logger = logging.getLogger("flowra_care.checkin")


def _build_engine(ai_consent: bool) -> PsychiatricRiskEngine:
    # LGPD-4 — só usa o analisador externo (LLM) com o consentimento de IA do paciente.
    return PsychiatricRiskEngine(free_text_analyzer=analyzer_for(ai_consent))


async def _transcribe_audio(session: AsyncSession, patient: Patient, audio_url: str | None) -> str | None:
    """Transcreve o áudio do check-in (se houver anexo do paciente e transcrição ativa)."""
    # LGPD-4 — a transcrição envia áudio a um provedor externo; exige consentimento
    # de IA do paciente. Sem ele, o áudio não é transcrito (e o CL-2 escala p/ AMARELO).
    if not patient.ai_consent:
        return None
    attachment_id = attachment_id_from_ref(audio_url)
    if attachment_id is None:
        return None
    attachment = await session.get(Attachment, attachment_id)
    if attachment is None or attachment.patient_id != patient.id:
        return None
    data = load_bytes(attachment)
    if data is None:
        return None
    return await transcribe(data, attachment.content_type, attachment.filename or "audio")


async def process_checkin(
    session: AsyncSession, patient: Patient, payload: CheckInCreate, *, when: datetime | None = None
) -> CheckIn:
    engine = _build_engine(patient.ai_consent)
    # Transcrição do áudio (se habilitada) entra no texto livre analisado pelo risco —
    # de forma conservadora, sem substituir o que o paciente escreveu.
    transcript = await _transcribe_audio(session, patient, payload.audio_url)
    effective_text = "\n".join(t for t in (payload.free_text, transcript) if t) or None

    # CL-2 — o check-in trouxe áudio mas ele não foi transcrito/analisado (transcrição
    # desligada por padrão, ou falha). O motor não pode concluir "verde" sem ter olhado
    # o áudio: sinalizamos para escalar a no mínimo AMARELO e pedir revisão manual.
    audio_unanalyzed = bool(payload.audio_url) and transcript is None

    # O analisador de texto livre pode chamar um LLM (I/O bloqueante); roda numa
    # thread para não bloquear o event loop. As regras determinísticas são leves.
    assessment = await asyncio.to_thread(
        engine.assess,
        payload.structured_responses,
        effective_text,
        audio_unanalyzed=audio_unanalyzed,
    )

    checkin = CheckIn(
        patient_id=patient.id,
        protocol_id=patient.active_protocol_id,
        structured_responses=payload.structured_responses,
        free_text=payload.free_text,
        audio_url=payload.audio_url,
        audio_transcript=transcript,
        risk_level=assessment.level,
        risk_reasons=assessment.reasons,
        category_risks=assessment.category_risks,
    )
    # Check-in retroativo (dia esquecido): grava com a data informada.
    if when is not None:
        checkin.created_at = when
    session.add(checkin)
    await session.flush()  # garante checkin.id para o alerta e a auditoria

    # Risco por tendência: combina o risco pontual (deste check-in) com o padrão
    # dos check-ins recentes, mantendo o MAIOR risco (conservador).
    trend = await _assess_trend(session, patient, checkin, assessment.level)
    combined_level = assessment.level.escalate(trend.level)
    combined_reasons = assessment.reasons + trend.reasons

    # Atualiza o índice de risco atual só se ESTE for o check-in mais recente —
    # um retroativo de um dia antigo não pode rebaixar o risco/última data atuais.
    effective_time = when or datetime.now(timezone.utc)
    if patient.last_checkin_at is None or effective_time >= patient.last_checkin_at:
        patient.current_risk = combined_level
        patient.last_checkin_at = effective_time

    await audit.record(
        session,
        action=AuditAction.CHECKIN_SUBMITTED,
        actor=f"patient:{patient.id}",
        entity_type="checkin",
        entity_id=checkin.id,
    )
    # LGPD — o log de auditoria é retido mesmo após a eliminação do paciente
    # (proteção jurídica). Por isso NÃO gravamos aqui conteúdo clínico/texto livre
    # (ex.: sinais derivados do relato do paciente); apenas os níveis de risco, que
    # são o mínimo necessário para auditar que o cálculo ocorreu. O detalhe clínico
    # vive no check-in/alerta, que são apagados em cascata na eliminação.
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
        },
    )

    # Alerta apenas quando o risco (pontual ou de tendência) exige atenção (🟠/🔴).
    alert: Alert | None = None
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

    # CL-3 — durabilidade ANTES de notificar. Persistimos check-in + risco + alerta
    # com um commit explícito e só DEPOIS notificamos. Uma falha de notificação
    # (ex.: timeout do push da Expo) NUNCA pode derrubar a transação e fazer o
    # check-in 🔴 e o alerta sumirem sem o médico ser avisado. (Antes, dispatch_alert
    # rodava dentro da mesma transação: qualquer erro no envio descartava tudo.)
    await session.commit()

    if alert is not None:
        try:
            email, phone = await doctor_notification_contacts(session, patient)
            await dispatch_alert(session, alert=alert, patient=patient, email=email, phone=phone)
            await session.commit()
        except Exception:  # noqa: BLE001 — notificar é best-effort; o alerta já está salvo
            logger.exception(
                "Falha ao despachar o alerta %s (paciente=%s). O alerta ESTÁ "
                "persistido e visível no painel; apenas a notificação externa falhou.",
                alert.id, patient.id,
            )
            await session.rollback()

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
