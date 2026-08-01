"""Serviço de lembretes de medicação: geração das doses do dia e adesão.

As "tomadas" (intakes) do dia são geradas de forma preguiçosa quando o app busca
os lembretes — evita precisar de um agendador rodando para o MVP. A entrega por
push/WhatsApp (com agendador) pluga depois na abstração de canais.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.alert import Alert
from app.models.enums import (
    AlertStatus,
    AlertUrgency,
    AuditAction,
    MedicationIntakeStatus,
    RiskLevel,
)
from app.models.medication import MedicationIntake, MedicationPlan
from app.models.patient import Patient
from app.services import audit
from app.services.notifications import dispatch_alert, doctor_notification_contacts, send_plain
from app.services.push_service import push_to_patient


def _day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


async def generate_today_intakes(
    session: AsyncSession, patient: Patient
) -> list[tuple[MedicationIntake, MedicationPlan]]:
    """Garante as tomadas de hoje dos planos ativos e retorna (intake, plano)."""
    now = datetime.now(timezone.utc)
    today = now.date()
    start, end = _day_bounds(now)

    plans = list(
        (
            await session.execute(
                select(MedicationPlan).where(
                    MedicationPlan.patient_id == patient.id,
                    MedicationPlan.active.is_(True),
                    MedicationPlan.start_date <= today,
                )
            )
        )
        .scalars()
        .all()
    )
    plans = [p for p in plans if p.end_date is None or p.end_date >= today]
    plan_by_id = {p.id: p for p in plans}

    # Tomadas já existentes hoje (para não duplicar).
    existing = {
        (i.plan_id, i.scheduled_for)
        for i in (
            await session.execute(
                select(MedicationIntake).where(
                    MedicationIntake.patient_id == patient.id,
                    MedicationIntake.scheduled_for >= start,
                    MedicationIntake.scheduled_for < end,
                )
            )
        )
        .scalars()
        .all()
    }

    for plan in plans:
        for hhmm in plan.times:
            hh, mm = (int(x) for x in hhmm.split(":"))
            scheduled_for = datetime.combine(today, time(hh, mm), tzinfo=timezone.utc)
            if (plan.id, scheduled_for) in existing:
                continue
            session.add(
                MedicationIntake(
                    tenant_id=plan.tenant_id,
                    plan_id=plan.id,
                    patient_id=patient.id,
                    scheduled_for=scheduled_for,
                )
            )
    await session.flush()

    result = await session.execute(
        select(MedicationIntake)
        .where(
            MedicationIntake.patient_id == patient.id,
            MedicationIntake.scheduled_for >= start,
            MedicationIntake.scheduled_for < end,
        )
        .order_by(MedicationIntake.scheduled_for)
    )
    return [(i, plan_by_id[i.plan_id]) for i in result.scalars().all() if i.plan_id in plan_by_id]


async def maybe_alert_missed_streak(session: AsyncSession, plan: MedicationPlan) -> Alert | None:
    """Alerta o médico quando o paciente falta N doses seguidas de um plano.

    Considera apenas doses já resolvidas (não 'pending'); 'taken'/'later' quebram a
    sequência. Alerta uma única vez, no momento em que a sequência atinge N.
    """
    n = settings.medication_missed_alert_streak
    recent = list(
        (
            await session.execute(
                select(MedicationIntake)
                .where(
                    MedicationIntake.plan_id == plan.id,
                    MedicationIntake.status != MedicationIntakeStatus.PENDING,
                )
                .order_by(MedicationIntake.scheduled_for.desc())
                .limit(n)
            )
        )
        .scalars()
        .all()
    )
    if len(recent) < n or any(i.status is not MedicationIntakeStatus.MISSED for i in recent):
        return None

    # Dedup: só um alerta em aberto de faltas por plano (até o médico resolvê-lo).
    marker = f"medication_plan:{plan.id}"
    already_open = await session.scalar(
        select(Alert.id).where(
            Alert.patient_id == plan.patient_id,
            Alert.status != AlertStatus.RESOLVED,
            Alert.reasons_detail.contains([marker]),
        )
    )
    if already_open is not None:
        return None

    patient = await session.get(Patient, plan.patient_id)
    if patient is None:
        return None
    reason = f"Não tomou {plan.name} {n} vezes seguidas"
    alert = Alert(
        patient_id=patient.id,
        checkin_id=None,
        level=RiskLevel.ORANGE,
        urgency=AlertUrgency.ROUTINE,
        reason=reason,
        reasons_detail=[reason, f"medication_plan:{plan.id}"],
    )
    session.add(alert)
    await session.flush()
    await audit.record(
        session,
        action=AuditAction.ALERT_CREATED,
        actor="system",
        entity_type="alert",
        entity_id=alert.id,
        metadata={"kind": "medication_missed_streak", "plan_id": str(plan.id), "streak": n},
    )
    email, phone = await doctor_notification_contacts(session, patient)
    await dispatch_alert(session, alert=alert, patient=patient, email=email, phone=phone)
    return alert


def _reminder_message(plan: MedicationPlan) -> tuple[str, str]:
    subject = "[Flowra Care] Hora do seu medicamento"
    body = (
        f"Está na hora de tomar {plan.name} ({plan.dose}).\n\n"
        "Abra o app para confirmar: ✓ tomei / ⏰ vou tomar depois / ❌ não tomei."
    )
    return subject, body


async def scan_due_medications(session: AsyncSession) -> dict:
    """Agendador (cron): cria as doses que venceram, envia lembrete e marca como
    'não tomou' as doses pendentes de dias anteriores. Idempotente via reminded_at.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    plans = list(
        (
            await session.execute(
                select(MedicationPlan).where(
                    MedicationPlan.active.is_(True),
                    MedicationPlan.start_date <= today,
                )
            )
        )
        .scalars()
        .all()
    )
    plans = [p for p in plans if p.end_date is None or p.end_date >= today]
    plan_by_id = {p.id: p for p in plans}

    existing = {
        (i.plan_id, i.scheduled_for)
        for i in (
            await session.execute(
                select(MedicationIntake).where(
                    MedicationIntake.scheduled_for >= start_today,
                    MedicationIntake.scheduled_for < start_today + timedelta(days=1),
                )
            )
        )
        .scalars()
        .all()
    }

    # 1. Cria as doses cujo horário já chegou hoje.
    for plan in plans:
        for hhmm in plan.times:
            hh, mm = (int(x) for x in hhmm.split(":"))
            scheduled_for = datetime.combine(today, time(hh, mm), tzinfo=timezone.utc)
            if scheduled_for > now or (plan.id, scheduled_for) in existing:
                continue
            session.add(
                MedicationIntake(
                    tenant_id=plan.tenant_id,
                    plan_id=plan.id,
                    patient_id=plan.patient_id,
                    scheduled_for=scheduled_for,
                )
            )
    await session.flush()

    # 2. Envia lembrete das doses vencidas ainda pendentes e não lembradas.
    due = list(
        (
            await session.execute(
                select(MedicationIntake).where(
                    MedicationIntake.scheduled_for <= now,
                    MedicationIntake.scheduled_for >= start_today,
                    MedicationIntake.status == MedicationIntakeStatus.PENDING,
                    MedicationIntake.reminded_at.is_(None),
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
                select(Patient).where(Patient.id.in_([i.patient_id for i in due] or [uuid.uuid4()]))
            )
        )
        .scalars()
        .all()
    }
    reminders = 0
    for intake in due:
        patient = patients.get(intake.patient_id)
        plan = plan_by_id.get(intake.plan_id)
        if plan is not None:
            subject, body = _reminder_message(plan)
            if patient is not None and patient.contact:
                await send_plain(target=patient.contact, subject=subject, body=body)
            await push_to_patient(session, intake.patient_id, subject, body)
        intake.reminded_at = now
        reminders += 1

    # 3. Marca como 'não tomou' as doses pendentes de dias anteriores.
    overdue = list(
        (
            await session.execute(
                select(MedicationIntake).where(
                    MedicationIntake.status == MedicationIntakeStatus.PENDING,
                    MedicationIntake.scheduled_for < start_today,
                )
            )
        )
        .scalars()
        .all()
    )
    for intake in overdue:
        intake.status = MedicationIntakeStatus.MISSED
    await session.flush()

    # 4. Alerta o médico quando há N faltas seguidas em um plano.
    missed_alerts = 0
    for plan_id in {i.plan_id for i in overdue}:
        plan = plan_by_id.get(plan_id) or await session.get(MedicationPlan, plan_id)
        if plan is not None and await maybe_alert_missed_streak(session, plan):
            missed_alerts += 1

    return {
        "reminders": reminders,
        "marked_missed": len(overdue),
        "missed_alerts": missed_alerts,
    }


async def adherence_summary(
    session: AsyncSession, patient_id: uuid.UUID, days: int = 30
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    intakes = list(
        (
            await session.execute(
                select(MedicationIntake).where(
                    MedicationIntake.patient_id == patient_id,
                    MedicationIntake.scheduled_for >= since,
                )
            )
        )
        .scalars()
        .all()
    )
    counts = {s: 0 for s in MedicationIntakeStatus}
    for i in intakes:
        counts[i.status] += 1
    responded = (
        counts[MedicationIntakeStatus.TAKEN]
        + counts[MedicationIntakeStatus.LATER]
        + counts[MedicationIntakeStatus.MISSED]
    )
    rate = counts[MedicationIntakeStatus.TAKEN] / responded if responded else 0.0
    return {
        "total": len(intakes),
        "taken": counts[MedicationIntakeStatus.TAKEN],
        "later": counts[MedicationIntakeStatus.LATER],
        "missed": counts[MedicationIntakeStatus.MISSED],
        "pending": counts[MedicationIntakeStatus.PENDING],
        "adherence_rate": round(rate, 3),
    }
