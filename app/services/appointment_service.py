"""Lembretes de consulta ("consulta amanhã") via agendador.

Avisa o paciente das consultas abertas dentro da janela de antecedência
(APPOINTMENT_REMINDER_HOURS). Idempotente via reminder_sent_at. A entrega usa a
abstração de canais (log/whatsapp/…); o push pluga quando o app for definido.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.appointment import Appointment
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.services.notifications import send_plain
from app.services.push_service import push_to_patient

_OPEN = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)


def _message(appt: Appointment) -> tuple[str, str]:
    when = appt.scheduled_at.strftime("%d/%m às %H:%M (UTC)")
    label = "consulta" if appt.kind.value == "consultation" else "retorno"
    local = f"\nLocal: {appt.location}" if appt.location else ""
    subject = "[Flowra Care] Lembrete de consulta"
    body = f"Você tem um(a) {label} em {when}.{local}\n\nAbra o app para confirmar sua presença."
    return subject, body


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
    for appt in appts:
        patient = patients.get(appt.patient_id)
        subject, body = _message(appt)
        if patient is not None and patient.contact:
            await send_plain(target=patient.contact, subject=subject, body=body)
        await push_to_patient(session, appt.patient_id, subject, body)
        appt.reminder_sent_at = now
        sent += 1
    return {"reminders": sent}
