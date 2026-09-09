"""Rotas do app do paciente — autenticadas por token opaco (X-Patient-Token)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_patient
from app.core.config import settings
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.checkin import CheckIn
from app.models.enums import (
    AppointmentStatus,
    DeviceOwnerType,
    MedicationIntakeStatus,
    MessageSender,
    MessageThread,
    PrescriptionStatus,
)
from app.models.exam import Exam
from app.models.medication import MedicationIntake, MedicationPlan
from app.models.message import Message
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.protocol import Protocol
from app.protocol.validation import validate_responses
from app.schemas.appointment import AppointmentRead, RescheduleRequest
from app.schemas.checkin import CalendarDay, CheckInCreate, CheckInResult
from app.schemas.device import DeviceRegister, DeviceTokenRead
from app.schemas.exam import ExamRead
from app.schemas.message import MessageCreate, MessageRead
from app.schemas.prescription import PrescriptionRead
from app.services.push_service import push_to_doctor, register_device, unregister_device
from app.schemas.medication import (
    MedicationDoseToday,
    MedicationIntakeRead,
    MedicationIntakeRespond,
)
from app.schemas.patient import PatientToday
from app.schemas.protocol import ProtocolRead
from app.services.ai_chat_service import patient_ai_reply
from app.services.checkin_service import process_checkin
from app.services.medication_service import generate_today_intakes, maybe_alert_missed_streak

router = APIRouter(prefix="/patient", tags=["patient-app"])


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.checkin_timezone)


def _today_local() -> date:
    return datetime.now(_tz()).date()


def _day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    """Intervalo [início, fim) do dia local `d`, em UTC (created_at é gravado em UTC)."""
    tz = _tz()
    start_local = datetime(d.year, d.month, d.day, tzinfo=tz)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _local_noon_utc(d: date) -> datetime:
    """Meio-dia local de `d` em UTC — usado como created_at de um check-in retroativo
    (fica com folga dentro do dia, independente do fuso)."""
    return datetime(d.year, d.month, d.day, 12, tzinfo=_tz()).astimezone(timezone.utc)


def _start_of_day_utc() -> datetime:
    """Início do dia CORRENTE no fuso configurado, em UTC."""
    return _day_bounds_utc(_today_local())[0]


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
    """Envio do check-in do paciente (< 1 min). Sem data = hoje; com `for_date`
    permite responder um dia esquecido (retroativo), dentro da janela."""
    today = _today_local()
    target = payload.for_date or today

    # Não permite futuro.
    if target > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível responder um dia que ainda não chegou.",
        )
    # Retroativo: só dentro da janela configurada.
    days_back = (today - target).days
    if days_back > settings.checkin_backfill_days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Só dá para responder até {settings.checkin_backfill_days} dias atrás.",
        )

    # Idempotência: um check-in por dia (no dia-alvo). Reenvios recebem 409.
    day_start, day_end = _day_bounds_utc(target)
    already = await session.scalar(
        select(
            exists().where(
                CheckIn.patient_id == patient.id,
                CheckIn.created_at >= day_start,
                CheckIn.created_at < day_end,
            )
        )
    )
    if already:
        msg = (
            "Você já registrou seu check-in hoje."
            if target == today
            else "Você já respondeu esse dia."
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)

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

    # Retroativo grava com o meio-dia local do dia-alvo; hoje usa o horário atual.
    when = None if target == today else _local_noon_utc(target)
    checkin = await process_checkin(session, patient, payload, when=when)
    # Retorno propositalmente neutro: não devolvemos o risco ao paciente.
    return CheckInResult(
        id=checkin.id,
        received_at=checkin.created_at or datetime.now(timezone.utc),
        message=(
            "Check-in recebido. Obrigado por responder hoje."
            if target == today
            else "Check-in do dia registrado. Obrigado!"
        ),
    )


def _mood_of(responses: dict | None) -> int | None:
    """Humor (código estável "mood") daquele dia, se registrado — para o calendário."""
    value = (responses or {}).get("mood")
    try:
        return int(float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


@router.get("/checkins/calendar", response_model=list[CalendarDay])
async def checkin_calendar(
    days: int = Query(35, ge=1, le=90),
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[CalendarDay]:
    """Calendário dos últimos `days` dias: respondido/faltou + humor do dia."""
    today = _today_local()
    start_date = today - timedelta(days=days - 1)
    start_utc = _day_bounds_utc(start_date)[0]
    end_utc = _day_bounds_utc(today)[1]
    result = await session.execute(
        select(CheckIn)
        .where(
            CheckIn.patient_id == patient.id,
            CheckIn.created_at >= start_utc,
            CheckIn.created_at < end_utc,
        )
    )
    tz = _tz()
    by_date: dict[date, int | None] = {}
    for c in result.scalars().all():
        local_day = c.created_at.astimezone(tz).date()
        by_date[local_day] = _mood_of(c.structured_responses)

    out: list[CalendarDay] = []
    for i in range(days):
        d = start_date + timedelta(days=i)
        checked = d in by_date
        is_today = d == today
        days_back = (today - d).days
        out.append(
            CalendarDay(
                date=d,
                checked_in=checked,
                can_fill=(not checked) and 0 < days_back <= settings.checkin_backfill_days,
                is_today=is_today,
                mood=by_date.get(d),
            )
        )
    return out


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
    appt.reschedule_requested_at = None  # confirmar limpa qualquer pedido de remarcação
    appt.reschedule_note = None
    return appt


@router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentRead)
async def request_reschedule(
    appointment_id: uuid.UUID,
    payload: RescheduleRequest,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> Appointment:
    """Paciente pede para remarcar. Não muda o horário (quem reagenda é o médico):
    registra o pedido e avisa o médico para propor um novo horário."""
    appt = await session.get(Appointment, appointment_id)
    if appt is None or appt.patient_id != patient.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
    if appt.status is AppointmentStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Consulta cancelada. Fale com seu médico para remarcar.",
        )
    appt.reschedule_requested_at = datetime.now(timezone.utc)
    appt.reschedule_note = (payload.note or "").strip() or None
    await session.flush()
    # LGPD — minimização: sem nome/detalhe no push (aparece em tela de bloqueio).
    await push_to_doctor(
        session, appt.doctor_id,
        "[Flowra Care] Pedido de remarcação",
        "Um paciente pediu para remarcar uma consulta. Abra o painel.",
    )
    return appt


@router.get("/exams", response_model=list[ExamRead])
async def my_exams(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[Exam]:
    """Exames do paciente (solicitados e disponíveis)."""
    result = await session.execute(
        select(Exam).where(Exam.patient_id == patient.id).order_by(Exam.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/prescriptions", response_model=list[PrescriptionRead])
async def my_prescriptions(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[Prescription]:
    """Receitas emitidas do paciente (histórico)."""
    result = await session.execute(
        select(Prescription)
        .where(
            Prescription.patient_id == patient.id,
            Prescription.status == PrescriptionStatus.ISSUED,
        )
        .order_by(Prescription.issued_at.desc())
    )
    return list(result.scalars().all())


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionRead)
async def my_prescription(
    prescription_id: uuid.UUID,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> Prescription:
    presc = await session.get(Prescription, prescription_id)
    if presc is None or presc.patient_id != patient.id or presc.status is not PrescriptionStatus.ISSUED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receita não encontrada.")
    return presc


@router.post("/devices", response_model=DeviceTokenRead, status_code=status.HTTP_201_CREATED)
async def register_patient_device(
    payload: DeviceRegister,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> DeviceTokenRead:
    """Registra o device token do paciente para receber push."""
    device = await register_device(
        session, owner_type=DeviceOwnerType.PATIENT, owner_id=patient.id,
        token=payload.token, platform=payload.platform,
    )
    return DeviceTokenRead.model_validate(device)


@router.post("/devices/unregister", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_patient_device(
    payload: DeviceRegister,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> None:
    await unregister_device(
        session, owner_type=DeviceOwnerType.PATIENT, owner_id=patient.id, token=payload.token,
    )


@router.post("/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def send_patient_message(
    payload: MessageCreate,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> Message:
    """Paciente envia mensagem ao médico responsável."""
    message = Message(
        tenant_id=patient.tenant_id, patient_id=patient.id, doctor_id=patient.doctor_id,
        sender=MessageSender.PATIENT, body=payload.body, attachments=payload.attachments,
    )
    session.add(message)
    await session.flush()
    # LGPD — minimização: sem nome do paciente no push (aparece em tela de bloqueio).
    await push_to_doctor(
        session, patient.doctor_id,
        "[Flowra Care] Nova mensagem", "Um paciente enviou uma mensagem. Abra o painel.",
    )
    return message


@router.get("/messages", response_model=list[MessageRead])
async def list_patient_messages(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[Message]:
    result = await session.execute(
        select(Message)
        .where(
            Message.patient_id == patient.id,
            Message.doctor_id == patient.doctor_id,
            Message.thread == MessageThread.CARE,
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    messages = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    for m in messages:
        if m.sender is MessageSender.DOCTOR and m.read_at is None:
            m.read_at = now
    return messages


@router.post("/ai-chat", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def ai_chat(
    payload: MessageCreate,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> Message:
    """Paciente conversa com a IA de apoio; a IA responde (e alerta o médico em risco)."""
    return await patient_ai_reply(session, patient, payload.body)


@router.get("/ai-chat", response_model=list[MessageRead])
async def list_ai_chat(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[Message]:
    """Histórico da conversa do paciente com a IA."""
    result = await session.execute(
        select(Message)
        .where(Message.patient_id == patient.id, Message.thread == MessageThread.AI)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
