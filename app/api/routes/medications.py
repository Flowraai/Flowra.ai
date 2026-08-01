"""Rotas de lembretes de medicação (lado do médico)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.medication import MedicationPlan
from app.models.patient import Patient
from app.schemas.medication import (
    MedicationAdherence,
    MedicationPlanCreate,
    MedicationPlanRead,
    MedicationPlanUpdate,
)
from app.services.medication_service import adherence_summary

router = APIRouter(tags=["medications"])


async def _owned_patient(session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_plan(session: AsyncSession, doctor: Doctor, plan_id: uuid.UUID) -> MedicationPlan:
    plan = await session.get(MedicationPlan, plan_id)
    if plan is not None:
        patient = await session.get(Patient, plan.patient_id)
        if patient is not None and patient.doctor_id == doctor.id:
            return plan
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado.")


@router.post(
    "/patients/{patient_id}/medications",
    response_model=MedicationPlanRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_plan(
    patient_id: uuid.UUID,
    payload: MedicationPlanCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> MedicationPlan:
    patient = await _owned_patient(session, doctor, patient_id)
    plan = MedicationPlan(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        name=payload.name,
        dose=payload.dose,
        times=payload.times,
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
    )
    session.add(plan)
    await session.flush()
    return plan


@router.get("/patients/{patient_id}/medications", response_model=list[MedicationPlanRead])
async def list_plans(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[MedicationPlan]:
    await _owned_patient(session, doctor, patient_id)
    result = await session.execute(
        select(MedicationPlan)
        .where(MedicationPlan.patient_id == patient_id)
        .order_by(MedicationPlan.created_at.desc())
    )
    return list(result.scalars().all())


@router.patch("/medications/{plan_id}", response_model=MedicationPlanRead)
async def update_plan(
    plan_id: uuid.UUID,
    payload: MedicationPlanUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> MedicationPlan:
    plan = await _owned_plan(session, doctor, plan_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    return plan


@router.get(
    "/patients/{patient_id}/medications/adherence", response_model=MedicationAdherence
)
async def patient_adherence(
    patient_id: uuid.UUID,
    days: int = 30,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> MedicationAdherence:
    await _owned_patient(session, doctor, patient_id)
    return MedicationAdherence(**await adherence_summary(session, patient_id, min(days, 365)))
