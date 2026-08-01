"""Rotas de consultas/retornos (lado do médico)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus
from app.models.patient import Patient
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentUpdate

router = APIRouter(tags=["appointments"])

_OPEN = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)


async def _owned_patient(session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_appointment(
    session: AsyncSession, doctor: Doctor, appointment_id: uuid.UUID
) -> Appointment:
    appt = await session.get(Appointment, appointment_id)
    if appt is None or appt.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
    return appt


@router.post(
    "/patients/{patient_id}/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    patient_id: uuid.UUID,
    payload: AppointmentCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Appointment:
    patient = await _owned_patient(session, doctor, patient_id)
    appt = Appointment(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        scheduled_at=payload.scheduled_at,
        kind=payload.kind,
        location=payload.location,
        notes=payload.notes,
    )
    session.add(appt)
    await session.flush()
    return appt


@router.get("/patients/{patient_id}/appointments", response_model=list[AppointmentRead])
async def list_patient_appointments(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[Appointment]:
    await _owned_patient(session, doctor, patient_id)
    result = await session.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc())
    )
    return list(result.scalars().all())


@router.get("/appointments/upcoming", response_model=list[AppointmentRead])
async def upcoming_appointments(
    limit: int = Query(50, ge=1, le=200),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[Appointment]:
    """Próximas consultas do médico (agendadas/confirmadas), da mais próxima."""
    result = await session.execute(
        select(Appointment)
        .where(
            Appointment.doctor_id == doctor.id,
            Appointment.status.in_(_OPEN),
            Appointment.scheduled_at >= datetime.now(timezone.utc),
        )
        .order_by(Appointment.scheduled_at)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.patch("/appointments/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Appointment:
    appt = await _owned_appointment(session, doctor, appointment_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(appt, field, value)
    return appt
