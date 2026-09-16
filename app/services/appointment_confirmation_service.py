"""Mensagem de confirmação da consulta (ao agendar e pelo botão da Agenda).

Diferente do lembrete (24h antes), a confirmação sai **na hora do agendamento** —
avisa o paciente do dia/hora e pede que ele confirme. O texto é configurável pelo
médico (template com placeholders); sem template, usa um padrão.

A entrega reaproveita `deliver_to_patient` (WhatsApp do médico → canais → log) e o
push do app. Marca `confirmation_sent_at` para a Agenda mostrar o estado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.schemas.doctor import MessagePrefs
from app.services.message_prefs import prefs_for_patient, with_signature
from app.services.notifications import deliver_to_patient
from app.services.push_service import push_to_patient

SUBJECT = "[Flowra Care] Confirmação de consulta"

# Placeholders aceitos no template. {local} já vem formatado ("📍 Sala 2" ou vazio).
DEFAULT_TEMPLATE = (
    "Olá {paciente}! Sua {tipo} está marcada para {data} às {hora}. {local}\n\n"
    "Responda SIM para confirmar. Se precisar remarcar, é só responder esta mensagem."
)


def _local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(settings.checkin_timezone))


def render_confirmation(
    appt: Appointment, patient: Patient, prefs: MessagePrefs
) -> tuple[str, str]:
    """Monta (assunto, corpo) da confirmação, aplicando o template e a assinatura."""
    when = _local(appt.scheduled_at)
    values = {
        "paciente": (patient.name or "").split(" ")[0] or "tudo bem",
        "tipo": "consulta" if appt.kind.value == "consultation" else "retorno",
        "data": when.strftime("%d/%m/%Y"),
        "hora": when.strftime("%H:%M"),
        "local": f"📍 {appt.location}" if appt.location else "",
    }
    template = (prefs.appointment_confirmation_template or "").strip() or DEFAULT_TEMPLATE
    body = template
    for key, val in values.items():
        body = body.replace("{" + key + "}", val)
    # Limpa sobras de placeholder vazio (ex.: espaço duplo quando não há local).
    body = "\n".join(" ".join(line.split()) for line in body.splitlines()).strip()
    return SUBJECT, with_signature(body, prefs)


async def send_confirmation(
    session: AsyncSession, appt: Appointment, patient: Patient | None = None
) -> bool:
    """Envia a confirmação ao paciente e marca `confirmation_sent_at`.

    Retorna True se pelo menos um canal foi acionado (WhatsApp/e-mail ou push).
    """
    if patient is None:
        patient = await session.get(Patient, appt.patient_id)
    if patient is None:
        return False
    prefs, _doctor = await prefs_for_patient(session, patient)
    subject, body = render_confirmation(appt, patient, prefs)

    delivered = False
    if patient.contact:
        delivered = await deliver_to_patient(session, patient, subject, body)
    await push_to_patient(session, appt.patient_id, subject, body)
    appt.confirmation_sent_at = datetime.now(timezone.utc)
    return delivered
