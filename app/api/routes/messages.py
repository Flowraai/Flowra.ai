"""Chat — lado do médico (mensagens com um paciente)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import MessageSender
from app.models.message import Message
from app.models.patient import Patient
from app.schemas.message import MessageCreate, MessageRead
from app.services.notifications import send_plain
from app.services.push_service import push_to_patient

router = APIRouter(tags=["chat"])


async def _owned_patient(session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


@router.post(
    "/patients/{patient_id}/messages", response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    patient_id: uuid.UUID,
    payload: MessageCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Message:
    patient = await _owned_patient(session, doctor, patient_id)
    message = Message(
        tenant_id=patient.tenant_id, patient_id=patient.id, doctor_id=doctor.id,
        sender=MessageSender.DOCTOR, body=payload.body, attachments=payload.attachments,
    )
    session.add(message)
    await session.flush()

    subject = "[Flowra Care] Nova mensagem do seu médico"
    body = "Você recebeu uma nova mensagem do seu médico. Abra o app para responder."
    if patient.contact:
        await send_plain(target=patient.contact, subject=subject, body=body)
    await push_to_patient(session, patient.id, subject, body)
    return message


@router.get("/patients/{patient_id}/messages", response_model=list[MessageRead])
async def list_messages(
    patient_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[Message]:
    await _owned_patient(session, doctor, patient_id)
    result = await session.execute(
        select(Message)
        .where(Message.patient_id == patient_id, Message.doctor_id == doctor.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = list(result.scalars().all())
    # Marca como lidas as mensagens do paciente ainda não lidas.
    now = datetime.now(timezone.utc)
    for m in messages:
        if m.sender is MessageSender.PATIENT and m.read_at is None:
            m.read_at = now
    return messages
