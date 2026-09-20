"""Chat — lado do médico (mensagens com um paciente)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, require_clinical_member
from app.db.session import get_db
from app.models.enums import ClinicRole, MessageSender, MessageThread
from app.models.message import Message
from app.models.patient import Patient
from app.schemas.message import MessageCreate, MessageRead
from app.services.notifications import deliver_whatsapp_status, send_plain
from app.services.push_service import push_to_patient

router = APIRouter(tags=["chat"])


def _scope_ok(row, member: CurrentMember) -> bool:
    """No escopo do membro? Médico vê o que é dele; dono vê a clínica inteira."""
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        return row.doctor_id == member.doctor.id
    return row.tenant_id == member.tenant_id


async def _owned_patient(
    session: AsyncSession, member: CurrentMember, patient_id: uuid.UUID
) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or not _scope_ok(patient, member):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


@router.post(
    "/patients/{patient_id}/messages", response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    patient_id: uuid.UUID,
    payload: MessageCreate,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Message:
    patient = await _owned_patient(session, member, patient_id)
    message = Message(
        tenant_id=patient.tenant_id, patient_id=patient.id, doctor_id=member.doctor.id,
        sender=MessageSender.DOCTOR, body=payload.body, attachments=payload.attachments,
    )
    session.add(message)
    await session.flush()

    delivery: str | None = None
    if payload.deliver:
        # Envio manual: entrega o TEXTO no WhatsApp do paciente e reporta o resultado.
        delivery = await deliver_whatsapp_status(session, patient, payload.body)
    # Aviso genérico quando NÃO houve entrega do texto por WhatsApp (o conteúdo
    # fica no app, sob login) — LGPD. Cobre o envio comum e o WhatsApp indisponível.
    if delivery != "whatsapp" and patient.contact:
        await send_plain(
            target=patient.contact,
            subject="[Flowra Care] Nova mensagem do seu médico",
            body="Você recebeu uma nova mensagem do seu médico. Abra o app para responder.",
        )
    # Push sempre genérico (aparece em tela de bloqueio) — sem conteúdo clínico.
    await push_to_patient(
        session, patient.id,
        "[Flowra Care] Nova mensagem do seu médico",
        "Você recebeu uma nova mensagem do seu médico. Abra o app para responder.",
    )
    # Campo transitório (não persistido) para o painel mostrar o resultado do envio.
    message.delivery = delivery  # type: ignore[attr-defined]
    return message


@router.get("/patients/{patient_id}/messages", response_model=list[MessageRead])
async def list_messages(
    patient_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> list[Message]:
    await _owned_patient(session, member, patient_id)
    result = await session.execute(
        select(Message)
        .where(
            Message.patient_id == patient_id,
            Message.thread == MessageThread.CARE,
        )
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
