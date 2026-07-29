"""Rotas do app do paciente — autenticadas por token opaco (X-Patient-Token)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_patient
from app.db.session import get_db
from app.models.checkin import CheckIn
from app.models.patient import Patient
from app.models.protocol import Protocol
from app.protocol.validation import validate_responses
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
    # Idempotência: um check-in por dia (limite do dia em UTC). Evita duplicatas que
    # distorceriam tendência e não-adesão; reenvios recebem 409.
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    already = await session.scalar(
        select(
            exists().where(
                CheckIn.patient_id == patient.id,
                CheckIn.created_at >= start_of_day,
            )
        )
    )
    if already:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você já registrou seu check-in hoje.",
        )

    # Valida as respostas contra o protocolo ativo antes de calcular o risco.
    if patient.active_protocol_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paciente sem protocolo ativo; não é possível registrar check-in.",
        )
    result = await session.execute(
        select(Protocol)
        .where(Protocol.id == patient.active_protocol_id)
        .options(selectinload(Protocol.questions))
    )
    protocol = result.scalar_one_or_none()
    if protocol is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Protocolo ativo não encontrado."
        )

    errors = validate_responses(protocol.questions, payload.structured_responses)
    if errors:
        raise HTTPException(
            status_code=422,  # Unprocessable Content
            detail={
                "message": "Respostas do check-in inválidas.",
                "errors": [e.as_dict() for e in errors],
            },
        )

    checkin = await process_checkin(session, patient, payload)
    # Retorno propositalmente neutro: não devolvemos o risco ao paciente.
    return CheckInResult(
        id=checkin.id,
        received_at=checkin.created_at or datetime.now(timezone.utc),
        message="Check-in recebido. Obrigado por responder hoje.",
    )
