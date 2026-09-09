"""Lembrete de consulta ("consulta amanhã") via agendador.

Avisa o paciente das consultas abertas dentro da janela de antecedência
(APPOINTMENT_REMINDER_HOURS, padrão 24h) e pede que ele **confirme a presença ou
peça para remarcar** pelo app. Idempotente via reminder_sent_at.

A entrega vai pelo WhatsApp do médico (se ele conectou o número) ou pelos canais
configurados — respeitando a preferência de mensagens do médico. Cada mensagem
pode levar a assinatura do médico.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.schemas.doctor import MessagePrefs
from app.services.message_prefs import prefs_for_patient, with_signature
from app.services.notifications import deliver_to_patient
from app.services.push_service import push_to_patient

_OPEN = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)


def _local(dt: datetime) -> datetime:
    """Converte o horário (UTC) para o fuso configurado, para exibir ao paciente."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(settings.checkin_timezone))


def _message(appt: Appointment, prefs: MessagePrefs) -> tuple[str, str]:
    when = _local(appt.scheduled_at).strftime("%d/%m às %H:%M")
    label = "consulta" if appt.kind.value == "consultation" else "retorno"
    local = f"\n📍 {appt.location}" if appt.location else ""
    link = (
        f"\n\nConfirme ou peça para remarcar aqui:\n{settings.patient_app_url_base}"
        if settings.patient_app_url_base
        else "\n\nAbra o app Flowra Care para confirmar ou pedir para remarcar."
    )
    subject = "[Flowra Care] Lembrete de consulta"
    body = (
        f"Olá! Você tem um(a) {label} marcada para {when}.{local}"
        f"{link}\n\n"
        "Você pode confirmar a presença ou pedir para remarcar."
    )
    return subject, with_signature(body, prefs)


async def scan_appointment_reminders(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=settings.appointment_reminder_hours)

    appts = list(
        (
            await session.execute(
                select(Appointment).where(
                    Appointment.status.in_(_OPEN),
                    Appointment.scheduled_at >= now,
                    Appointment.scheduled_at <= cutoff,
                    Appointment.reminder_sent_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    patients = {
        p.id: p
        for p in (
            await session.execute(
                select(Patient).where(
                    Patient.id.in_([a.patient_id for a in appts] or [uuid.uuid4()])
                )
            )
        )
        .scalars()
        .all()
    }

    sent = 0
    skipped = 0
    for appt in appts:
        patient = patients.get(appt.patient_id)
        # Preferência do médico: pode ter desligado o lembrete de consulta.
        prefs: MessagePrefs = MessagePrefs()
        if patient is not None:
            prefs, _doctor = await prefs_for_patient(session, patient)
        if not prefs.send_appointment_reminder:
            # Não reenvia nas próximas varreduras: marca como "tratado".
            appt.reminder_sent_at = now
            skipped += 1
            continue

        subject, body = _message(appt, prefs)
        if patient is not None and patient.contact:
            await deliver_to_patient(session, patient, subject, body)
        await push_to_patient(session, appt.patient_id, subject, body)
        appt.reminder_sent_at = now
        sent += 1
    return {"reminders": sent, "skipped_by_pref": skipped}
