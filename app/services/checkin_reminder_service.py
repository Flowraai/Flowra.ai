"""Lembrete diário de check-in — fecha o loop lembrete → check-in → resumo.

Uma vez por dia, a partir de uma hora configurada, avisa os pacientes ativos que
ainda não fizeram o check-in do dia (WhatsApp/e-mail + push). Dedupe por
`checkin_reminder_sent_at` (no máximo um lembrete por dia por paciente) e respeita
a preferência do médico (`send_checkin_reminder`).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.patient import Patient
from app.schemas.doctor import MessagePrefs
from app.services.message_prefs import prefs_for_patient, with_signature
from app.services.notifications import deliver_to_patient
from app.services.push_service import push_to_patient

_SUBJECT = "Flowra Care — check-in de hoje"
_BODY = (
    "Olá! Como você está hoje? Leva 1 minuto para registrar seu check-in no "
    "Flowra Care. Seu acompanhamento ajuda seu médico a cuidar melhor de você."
)


async def scan_checkin_reminders(session: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    # Só a partir da hora configurada (evita avisar de madrugada).
    if now.hour < settings.checkin_reminder_hour_utc:
        return {"reminders": 0, "skipped_by_pref": 0, "too_early": True}

    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    patients = list(
        (
            await session.execute(
                select(Patient).where(
                    Patient.is_active.is_(True),
                    # ainda não fez check-in hoje
                    or_(Patient.last_checkin_at.is_(None), Patient.last_checkin_at < start_of_day),
                    # ainda não foi lembrado hoje
                    or_(
                        Patient.checkin_reminder_sent_at.is_(None),
                        Patient.checkin_reminder_sent_at < start_of_day,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )

    sent = 0
    skipped = 0
    for patient in patients:
        prefs: MessagePrefs
        prefs, _doctor = await prefs_for_patient(session, patient)
        # Marca como tratado hoje de qualquer forma (evita reprocessar na próxima varredura).
        patient.checkin_reminder_sent_at = now
        if not prefs.send_checkin_reminder:
            skipped += 1
            continue
        body = with_signature(_BODY, prefs)
        if patient.contact:
            await deliver_to_patient(session, patient, _SUBJECT, body)
        await push_to_patient(session, patient.id, _SUBJECT, body)
        sent += 1

    return {"reminders": sent, "skipped_by_pref": skipped}
