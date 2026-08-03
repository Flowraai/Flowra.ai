"""Rotas de exames (lado do médico). Avisa o paciente quando fica disponível."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import ExamStatus
from app.models.exam import Exam
from app.models.patient import Patient
from app.schemas.exam import ExamCreate, ExamRead, ExamUpdate
from app.services.notifications import send_plain
from app.services.push_service import push_to_patient

router = APIRouter(tags=["exams"])


async def _owned_patient(session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_exam(session: AsyncSession, doctor: Doctor, exam_id: uuid.UUID) -> Exam:
    exam = await session.get(Exam, exam_id)
    if exam is None or exam.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exame não encontrado.")
    return exam


@router.post(
    "/patients/{patient_id}/exams", response_model=ExamRead, status_code=status.HTTP_201_CREATED
)
async def create_exam(
    patient_id: uuid.UUID,
    payload: ExamCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Exam:
    patient = await _owned_patient(session, doctor, patient_id)
    exam = Exam(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        name=payload.name,
        notes=payload.notes,
    )
    session.add(exam)
    await session.flush()
    return exam


@router.get("/patients/{patient_id}/exams", response_model=list[ExamRead])
async def list_exams(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[Exam]:
    await _owned_patient(session, doctor, patient_id)
    result = await session.execute(
        select(Exam).where(Exam.patient_id == patient_id).order_by(Exam.created_at.desc())
    )
    return list(result.scalars().all())


@router.patch("/exams/{exam_id}", response_model=ExamRead)
async def update_exam(
    exam_id: uuid.UUID,
    payload: ExamUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Exam:
    exam = await _owned_exam(session, doctor, exam_id)
    was_available = exam.status is ExamStatus.AVAILABLE
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(exam, field, value)

    # Ao ficar disponível, avisa o paciente uma única vez.
    if exam.status is ExamStatus.AVAILABLE and not was_available:
        if exam.available_at is None:
            exam.available_at = datetime.now(timezone.utc)
        if exam.notified_at is None:
            subject = "[Flowra Care] Resultado de exame disponível"
            body = (
                f"O resultado do seu exame ({exam.name}) já está disponível.\n\n"
                "Abra o app para visualizar."
            )
            patient = await session.get(Patient, exam.patient_id)
            if patient is not None and patient.contact:
                await send_plain(target=patient.contact, subject=subject, body=body)
            await push_to_patient(session, exam.patient_id, subject, body)
            exam.notified_at = datetime.now(timezone.utc)
    return exam
