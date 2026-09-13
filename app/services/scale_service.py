"""Escalas: aviso ao paciente e recorrência automática (agendador).

Quando o médico solicita uma escala, o paciente é avisado. Se a escala for
recorrente (recurring_days), o agendador recria uma nova aplicação a cada N dias
após a última resposta — sem o médico precisar lembrar.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clinical.scales import get_scale
from app.models.patient import Patient
from app.models.scale_entry import ScaleEntry
from app.services.notifications import deliver_to_patient
from app.services.push_service import push_to_patient


async def notify_patient(session: AsyncSession, patient: Patient, scale_name: str) -> None:
    """Avisa o paciente que há um questionário a responder (conteúdo não sensível)."""
    subject = "[Flowra Care] Novo questionário"
    body = (
        f"Seu médico pediu que você responda o questionário {scale_name} no app "
        "(menos de 2 minutos)."
    )
    if patient.contact:
        await deliver_to_patient(session, patient, subject, body)
    await push_to_patient(
        session, patient.id, subject, "Você tem um questionário para responder. Abra o app."
    )


async def scan_due_scales(session: AsyncSession) -> dict:
    """Agendador: recria escalas recorrentes vencidas e avisa os pacientes.

    Para cada (paciente, escala) com recorrência, se a última resposta foi há
    >= recurring_days e não há aplicação pendente, cria uma nova pendente.
    """
    now = datetime.now(timezone.utc)
    rows = list(
        (
            await session.execute(
                select(ScaleEntry).where(ScaleEntry.recurring_days.is_not(None))
            )
        )
        .scalars()
        .all()
    )

    pending: set[tuple] = set()
    latest_done: dict[tuple, ScaleEntry] = {}
    for e in rows:
        key = (e.patient_id, e.scale_code)
        if e.status == "pending":
            pending.add(key)
        elif e.status == "done" and e.completed_at is not None:
            cur = latest_done.get(key)
            if cur is None or e.completed_at > cur.completed_at:
                latest_done[key] = e

    created = 0
    for key, last in latest_done.items():
        if key in pending:
            continue
        due = last.completed_at + timedelta(days=last.recurring_days or 0)
        if due > now:
            continue
        patient = await session.get(Patient, last.patient_id)
        if patient is None or not patient.is_active:
            continue
        entry = ScaleEntry(
            tenant_id=last.tenant_id,
            patient_id=last.patient_id,
            doctor_id=last.doctor_id,
            scale_code=last.scale_code,
            status="pending",
            recurring_days=last.recurring_days,
            requested_at=now,
        )
        session.add(entry)
        await session.flush()
        scale = get_scale(last.scale_code)
        await notify_patient(session, patient, scale.name if scale else last.scale_code)
        created += 1

    return {"scales_created": created}
