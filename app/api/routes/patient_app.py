"""Rotas do app do paciente — autenticadas por token opaco (X-Patient-Token)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_patient
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.checkin import CheckIn
from app.models.enums import AppointmentStatus, MedicationIntakeStatus
from app.models.medication import MedicationIntake, MedicationPlan
from app.models.patient import Patient
from app.models.protocol import Protocol
from app.protocol.validation import validate_responses
from app.schemas.appointment import AppointmentRead
from app.schemas.checkin import CheckInCreate, CheckInResult
from app.schemas.medication import (
    MedicationDoseToday,
    MedicationIntakeRead,
    MedicationIntakeRespond,
)
from app.schemas.patient import PatientToday
from app.schemas.protocol import ProtocolRead
from app.services.checkin_service import process_checkin
from app.services.medication_service import generate_today_intakes, maybe_alert_missed_streak

router = APIRouter(prefix="/patient", tags=["patient-app"])


def _start_of_day_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("/today", response_model=PatientToday)
async def today(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> PatientToday:
    """Estado do dia: o app usa para mostrar o formulário ou o 'check-in feito'."""
    checked_in = await session.scalar(
        select(
            exists().where(
                CheckIn.patient_id == patient.id,
                CheckIn.created_at >= _start_of_day_utc(),
            )
        )
    )
    return PatientToday(
        patient_name=patient.name,
        checked_in_today=bool(checked_in),
        last_checkin_at=patient.last_checkin_at,
    )


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
    already = await session.scalar(
        select(
            exists().where(
                CheckIn.patient_id == patient.id,
                CheckIn.created_at >= _start_of_day_utc(),
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


@router.get("/medications/today", response_model=list[MedicationDoseToday])
async def medications_today(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[MedicationDoseToday]:
    """Lembretes de medicação de hoje (gera as tomadas do dia sob demanda)."""
    doses = await generate_today_intakes(session, patient)
    return [
        MedicationDoseToday(
            intake_id=intake.id,
            plan_id=plan.id,
            name=plan.name,
            dose=plan.dose,
            scheduled_for=intake.scheduled_for,
            status=intake.status,
        )
        for intake, plan in doses
    ]


@router.post("/medications/intakes/{intake_id}/respond", response_model=MedicationIntakeRead)
async def respond_intake(
    intake_id: uuid.UUID,
    payload: MedicationIntakeRespond,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> MedicationIntake:
    """Paciente responde a uma tomada: ✓ tomei / ⏰ depois / ❌ não tomei."""
    intake = await session.get(MedicationIntake, intake_id)
    if intake is None or intake.patient_id != patient.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tomada não encontrada.")
    intake.status = payload.status
    intake.responded_at = datetime.now(timezone.utc)
    await session.flush()

    # "Não tomei" pode fechar uma sequência de faltas → alerta ao médico.
    if payload.status is MedicationIntakeStatus.MISSED:
        plan = await session.get(MedicationPlan, intake.plan_id)
        if plan is not None:
            await maybe_alert_missed_streak(session, plan)

    return intake


@router.get("/appointments", response_model=list[AppointmentRead])
async def my_appointments(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[Appointment]:
    """Próximas consultas do paciente (agendadas/confirmadas)."""
    result = await session.execute(
        select(Appointment)
        .where(
            Appointment.patient_id == patient.id,
            Appointment.status.in_(
                (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)
            ),
            Appointment.scheduled_at >= datetime.now(timezone.utc),
        )
        .order_by(Appointment.scheduled_at)
    )
    return list(result.scalars().all())


@router.post("/appointments/{appointment_id}/confirm", response_model=AppointmentRead)
async def confirm_appointment(
    appointment_id: uuid.UUID,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> Appointment:
    """Paciente confirma a presença na consulta."""
    appt = await session.get(Appointment, appointment_id)
    if appt is None or appt.patient_id != patient.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
    if appt.status is AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Consulta cancelada não pode ser confirmada."
        )
    appt.status = AppointmentStatus.CONFIRMED
    return appt
