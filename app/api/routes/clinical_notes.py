"""Rotas de anotações clínicas (prontuário) — lado do médico."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, require_clinical_member
from app.api.patient_access import can_access_patient, can_access_resource
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.clinical_note import ClinicalNote
from app.models.enums import ClinicRole
from app.models.patient import Patient
from app.schemas.clinical_note import NoteCreate, NoteRead, NoteUpdate

router = APIRouter(tags=["clinical-notes"])


def _scope_ok(row, member: CurrentMember) -> bool:
    """No escopo do membro? Médico vê o que é dele; dono vê a clínica inteira."""
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        return row.doctor_id == member.doctor.id
    return row.tenant_id == member.tenant_id


async def _owned_patient(
    session: AsyncSession, member: CurrentMember, patient_id: uuid.UUID
) -> Patient:
    patient = await session.get(Patient, patient_id)
    if not await can_access_patient(session, member, patient):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_note(session: AsyncSession, member: CurrentMember, note_id: uuid.UUID) -> ClinicalNote:
    note = await session.get(ClinicalNote, note_id)
    if not await can_access_resource(session, member, note):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anotação não encontrada.")
    return note


@router.get("/patients/{patient_id}/notes", response_model=list[NoteRead])
async def list_notes(
    patient_id: uuid.UUID,
    appointment_id: uuid.UUID | None = Query(default=None),
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> list[ClinicalNote]:
    await _owned_patient(session, member, patient_id)
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
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> ClinicalNote:
    patient = await _owned_patient(session, member, patient_id)
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
        doctor_id=member.doctor.id,
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
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> ClinicalNote:
    note = await _owned_note(session, member, note_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(note, field, value)
    return note


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(
    note_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> None:
    note = await _owned_note(session, member, note_id)
    await session.delete(note)
