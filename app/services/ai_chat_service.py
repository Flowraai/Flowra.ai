"""Chat paciente↔IA: a IA responde e, por segurança, analisa o risco da mensagem.

Se a mensagem trouxer sinal de risco relevante (ex.: ideação suicida), gera um
alerta ao médico e responde com uma mensagem de segurança. A IA NÃO diagnostica.
"""

from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.enums import AlertUrgency, AuditAction, MessageSender, MessageThread, RiskLevel
from app.models.message import Message
from app.models.patient import Patient
from app.risk.free_text import get_free_text_analyzer
from app.services import audit
from app.services.llm import chat_complete
from app.services.notifications import dispatch_alert, doctor_notification_contacts

_SYSTEM = (
    "Você é um assistente de apoio do Flowra Care para pacientes psiquiátricos. "
    "Seja acolhedor, empático e breve (2-3 frases). Você NÃO é médico e NÃO dá "
    "diagnóstico nem prescrição; incentive o paciente a registrar o check-in diário e "
    "a conversar com o médico. Em emergência, oriente procurar ajuda imediata."
)
_SAFETY = (
    "Sinto muito que você esteja passando por isso — você não está sozinho(a). "
    "Se estiver pensando em se machucar, procure ajuda agora: ligue para o CVV no 188 "
    "(24h, gratuito) ou vá ao pronto-socorro mais próximo. Já avisei seu médico. "
    "Estou aqui com você."
)
_FALLBACK = (
    "Recebi sua mensagem, obrigado por compartilhar. Continue registrando seu check-in "
    "diário — seu médico acompanha tudo. Se precisar de algo urgente, fale com seu médico."
)


async def _alert_doctor(session: AsyncSession, patient: Patient, level: RiskLevel, signals: list) -> None:
    urgency = AlertUrgency.IMMEDIATE if level is RiskLevel.RED else AlertUrgency.ROUTINE
    reason = "Mensagem no chat com IA: " + ("; ".join(signals) or "sinal de risco")
    alert = Alert(
        patient_id=patient.id, checkin_id=None, level=level, urgency=urgency,
        reason=reason, reasons_detail=signals or [reason],
    )
    session.add(alert)
    await session.flush()
    await audit.record(
        session, action=AuditAction.ALERT_CREATED, actor="system",
        entity_type="alert", entity_id=alert.id, metadata={"kind": "ai_chat"},
    )
    email, phone = await doctor_notification_contacts(session, patient)
    await dispatch_alert(session, alert=alert, patient=patient, email=email, phone=phone)


async def patient_ai_reply(session: AsyncSession, patient: Patient, text: str) -> Message:
    """Persiste a mensagem do paciente, avalia risco e devolve a resposta da IA."""
    session.add(Message(
        tenant_id=patient.tenant_id, patient_id=patient.id, doctor_id=patient.doctor_id,
        sender=MessageSender.PATIENT, thread=MessageThread.AI, body=text,
    ))

    result = await asyncio.to_thread(get_free_text_analyzer().analyze, text)
    if result.level.order >= RiskLevel.ORANGE.order:
        await _alert_doctor(session, patient, result.level, result.signals)

    if result.level is RiskLevel.RED:
        reply = _SAFETY
    else:
        reply = await chat_complete(_SYSTEM, text) or _FALLBACK

    ai_message = Message(
        tenant_id=patient.tenant_id, patient_id=patient.id, doctor_id=patient.doctor_id,
        sender=MessageSender.AI, thread=MessageThread.AI, body=reply,
    )
    session.add(ai_message)
    await session.flush()
    return ai_message
