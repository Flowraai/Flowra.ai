"""Lançamentos financeiros por consulta: listar, gerar e receber/cancelar.

Camada de controle gerencial (a receber / recebido). Sem cobrança online no MVP.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.consultation_charge import ConsultationCharge
from app.models.doctor import Doctor
from app.models.health_plan import HealthPlan
from app.models.patient import Patient
from app.schemas.consultation_charge import ChargeRead, ChargeUpdate
from app.services.consultation_charge_service import compute_doctor_cents, generate_for_appointment

router = APIRouter(tags=["charges"])


async def _owned_patient(session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_charge(
    session: AsyncSession, doctor: Doctor, charge_id: uuid.UUID
) -> ConsultationCharge:
    charge = await session.get(ConsultationCharge, charge_id)
    if charge is None or charge.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lançamento não encontrado.")
    return charge


def _read(charge: ConsultationCharge, plan_name: str | None = None) -> ChargeRead:
    out = ChargeRead.model_validate(charge)
    out.health_plan_name = plan_name
    return out


@router.get("/patients/{patient_id}/charges", response_model=list[ChargeRead])
async def list_patient_charges(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[ChargeRead]:
    await _owned_patient(session, doctor, patient_id)
    rows = list(
        (
            await session.execute(
                select(ConsultationCharge)
                .where(ConsultationCharge.patient_id == patient_id)
                .order_by(ConsultationCharge.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    names = await _plan_names(session, rows)
    return [_read(c, names.get(c.health_plan_id)) for c in rows]


@router.post(
    "/appointments/{appointment_id}/charge",
    response_model=ChargeRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_charge(
    appointment_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> ChargeRead:
    """Gera o lançamento de uma consulta manualmente (idempotente).

    Útil para consultas realizadas antes de o financeiro existir.
    """
    appt = await session.get(Appointment, appointment_id)
    if appt is None or appt.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
    patient = await session.get(Patient, appt.patient_id)
    if patient is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    charge = await generate_for_appointment(session, appt, patient)
    plan_name = patient.health_plan.name if patient.health_plan else None
    return _read(charge, plan_name)


@router.patch("/charges/{charge_id}", response_model=ChargeRead)
async def update_charge(
    charge_id: uuid.UUID,
    payload: ChargeUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> ChargeRead:
    charge = await _owned_charge(session, doctor, charge_id)
    data = payload.model_dump(exclude_unset=True)

    if "gross_cents" in data:
        charge.gross_cents = data["gross_cents"]
        # Recalcula o repasse pela regra do convênio (ou = valor cheio no particular),
        # a menos que o médico informe doctor_cents explicitamente.
        if "doctor_cents" not in data:
            plan = (
                await session.get(HealthPlan, charge.health_plan_id)
                if charge.health_plan_id
                else None
            )
            charge.doctor_cents = compute_doctor_cents(charge.kind, charge.gross_cents, plan)
    if "doctor_cents" in data:
        charge.doctor_cents = data["doctor_cents"]
    if "notes" in data:
        charge.notes = data["notes"]
    if "payment_method" in data:
        charge.payment_method = data["payment_method"]
    if "status" in data:
        charge.status = data["status"]
        if data["status"] == "received":
            charge.received_at = charge.received_at or datetime.now(timezone.utc)
        else:
            charge.received_at = None

    plan_name = None
    if charge.health_plan_id:
        plan = await session.get(HealthPlan, charge.health_plan_id)
        plan_name = plan.name if plan else None
    return _read(charge, plan_name)


async def _plan_names(
    session: AsyncSession, charges: list[ConsultationCharge]
) -> dict[uuid.UUID, str]:
    ids = {c.health_plan_id for c in charges if c.health_plan_id}
    if not ids:
        return {}
    rows = (
        await session.execute(select(HealthPlan.id, HealthPlan.name).where(HealthPlan.id.in_(ids)))
    ).all()
    return {pid: name for pid, name in rows}
