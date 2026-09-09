"""Preferências das mensagens automáticas ao paciente (por médico).

Centraliza a leitura das preferências (o que enviar) e a aplicação da assinatura,
para que onboarding, lembretes de medicação e de consulta compartilhem a mesma
regra. Sem preferências salvas, o padrão é enviar tudo, sem assinatura.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.doctor import MessagePrefs


def prefs_of(doctor: Doctor | None) -> MessagePrefs:
    if doctor is None or not doctor.message_prefs:
        return MessagePrefs()
    try:
        return MessagePrefs(**doctor.message_prefs)
    except Exception:  # noqa: BLE001 — config inválida cai no padrão, nunca quebra o envio
        return MessagePrefs()


async def prefs_for_patient(
    session: AsyncSession, patient: Patient
) -> tuple[MessagePrefs, Doctor | None]:
    """(preferências, médico) do paciente — o médico já vem carregado para reuso."""
    doctor = await session.get(Doctor, patient.doctor_id)
    return prefs_of(doctor), doctor


def with_signature(body: str, prefs: MessagePrefs) -> str:
    """Acrescenta a assinatura do médico ao fim da mensagem, se houver."""
    signature = (prefs.signature or "").strip()
    if signature:
        return f"{body}\n\n— {signature}"
    return body
