"""Rotas de anotações clínicas (prontuário) — lado do médico."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.clinical_note import ClinicalNote
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.clinical_note import NoteCreate, NoteRead, NoteUpdate

router = APIRouter(tags=["clinical-notes"])


async def _owned_patient(session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_note(session: AsyncSession, doctor: Doctor, note_id: uuid.UUID) -> ClinicalNote:
    note = await session.get(ClinicalNote, note_id)
    if note is None or note.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anotação não encontrada.")
    return note


@router.get("/patients/{patient_id}/notes", response_model=list[NoteRead])
async def list_notes(
    patient_id: uuid.UUID,
    appointment_id: uuid.UUID | None = Query(default=None),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[ClinicalNote]:
    await _owned_patient(session, doctor, patient_id)
    stmt = select(ClinicalNote).where(ClinicalNote.patient_id == patient_id)
    if appointment_id is not None:
        stmt = stmt.where(ClinicalNote.appointment_id == appointment_id)
    stmt = stmt.order_by(ClinicalNote.created_at.desc())
    return list((await session.execute(stmt)).scalars().all())


@router.post(
    "/patients/{patient_id}/notes", response_model=NoteRead, status_code=status.HTTP_201_CREATED
)
async def create_note(
    patient_id: uuid.UUID,
    payload: NoteCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> ClinicalNote:
    patient = await _owned_patient(session, doctor, patient_id)
    # Se vinculado a uma consulta, ela precisa ser deste paciente.
    if payload.appointment_id is not None:
        appt = await session.get(Appointment, payload.appointment_id)
        if appt is None or appt.patient_id != patient.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Consulta inválida."
            )
    note = ClinicalNote(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_id=payload.appointment_id,
        kind=payload.kind,
        body=payload.body,
    )
    session.add(note)
    await session.flush()
    return note


@router.patch("/notes/{note_id}", response_model=NoteRead)
async def update_note(
    note_id: uuid.UUID,
    payload: NoteUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> ClinicalNote:
    note = await _owned_note(session, doctor, note_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    return note


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> None:
    note = await _owned_note(session, doctor, note_id)
    await session.delete(note)
