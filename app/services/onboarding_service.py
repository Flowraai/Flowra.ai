"""Onboarding do paciente: entrega do link de acesso pelo canal de notificação.

O paciente recebe automaticamente o plano/acesso (app/WhatsApp/notificação):
montamos um link com o token de acesso e enviamos ao contato do paciente pelos
canais configurados. Best-effort — nunca derruba o cadastro se o envio falhar.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.enums import AuditAction
from app.models.patient import Patient
from app.services import audit
from app.services.notifications import send_plain


def build_onboarding_link(raw_token: str) -> str:
    if settings.patient_app_url_base:
        return f"{settings.patient_app_url_base}?token={raw_token}"
    return f"Token de acesso: {raw_token}"


def _message(patient: Patient, raw_token: str) -> tuple[str, str]:
    subject = "[Flowra Care] Seu acompanhamento diário"
    body = (
        f"Olá, {patient.name}!\n\n"
        "Seu médico ativou o acompanhamento diário no Flowra Care. "
        "Todos os dias você responde um check-in rápido (menos de 1 minuto).\n\n"
        f"Acesse por aqui:\n{build_onboarding_link(raw_token)}\n\n"
        "Guarde este link — ele é pessoal e dá acesso ao seu check-in."
    )
    return subject, body


async def send_onboarding(
    session: AsyncSession, patient: Patient, raw_token: str
) -> bool:
    """Envia o onboarding ao contato do paciente. Retorna se houve destino/tentativa."""
    if not patient.contact:
        return False
    subject, body = _message(patient, raw_token)
    await send_plain(target=patient.contact, subject=subject, body=body)
    await audit.record(
        session,
        action=AuditAction.PATIENT_ONBOARDING_SENT,
        actor="system",
        entity_type="patient",
        entity_id=patient.id,
    )
    return True
