"""Rotas do app do paciente — autenticadas por token opaco (X-Patient-Token)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_patient
from app.db.session import get_db
from app.models.patient import Patient
from app.models.protocol import Protocol
from app.schemas.checkin import CheckInCreate, CheckInResult
from app.schemas.protocol import ProtocolRead
from app.services.checkin_service import process_checkin

router = APIRouter(prefix="/patient", tags=["patient-app"])


@router.get("/protocol", response_model=ProtocolRead)
async def my_protocol(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> Protocol:
    """Perguntas do dia que o app deve renderizar para este paciente."""
    if patient.active_protocol_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum protocolo ativo atribuído a este paciente.",
        )
    result = await session.execute(
        select(Protocol)
        .where(Protocol.id == patient.active_protocol_id)
        .options(selectinload(Protocol.questions))
    )
    protocol = result.scalar_one_or_none()
    if protocol is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocolo não encontrado.")
    return protocol


@router.post("/checkins", response_model=CheckInResult, status_code=status.HTTP_201_CREATED)
async def submit_checkin(
    payload: CheckInCreate,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> CheckInResult:
    """Envio do check-in diário do paciente (< 1 min)."""
    checkin = await process_checkin(session, patient, payload)
    # Retorno propositalmente neutro: não devolvemos o risco ao paciente.
    return CheckInResult(
        id=checkin.id,
        received_at=checkin.created_at or datetime.now(timezone.utc),
        message="Check-in recebido. Obrigado por responder hoje.",
    )
