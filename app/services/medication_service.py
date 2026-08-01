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

from app.models.enums import MedicationIntakeStatus
from app.models.medication import MedicationIntake, MedicationPlan
from app.models.patient import Patient


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
