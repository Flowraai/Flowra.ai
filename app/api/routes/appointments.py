"""Rotas de consultas/retornos (lado do médico)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, get_current_member, scope_query
from app.api.patient_access import patient_visible_clause
from app.db.session import get_db
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.enums import AppointmentStatus, ClinicRole
from app.models.patient import Patient
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentUpdate,
    PatientDirectoryItem,
)
from app.services.appointment_confirmation_service import send_confirmation
from app.services.consultation_charge_service import generate_for_appointment
from app.services.message_prefs import prefs_of

router = APIRouter(tags=["appointments"])

_OPEN = (AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED)


def _scope_ok(row, member: CurrentMember) -> bool:
    """A linha (paciente/consulta) está no escopo do membro?

    Médico vê o que é dele; dono/recepção veem a clínica inteira (agenda
    compartilhada). A agenda é operacional — recepção pode ver/gerir.
    """
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


async def _owned_appointment(
    session: AsyncSession, member: CurrentMember, appointment_id: uuid.UUID
) -> Appointment:
    appt = await session.get(Appointment, appointment_id)
    if appt is None or not _scope_ok(appt, member):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
    return appt


async def _with_names(
    session: AsyncSession, appts: list[Appointment]
) -> list[AppointmentRead]:
    """Serializa as consultas embutindo o nome do paciente (para a recepção ver a
    agenda sem tocar em dado clínico)."""
    ids = {a.patient_id for a in appts}
    names: dict[uuid.UUID, str] = {}
    if ids:
        # patient.name é EncryptedText — carregar via ORM decifra em memória.
        for p in (
            await session.execute(select(Patient).where(Patient.id.in_(ids)))
        ).scalars().all():
            names[p.id] = p.name
    out = []
    for a in appts:
        r = AppointmentRead.model_validate(a)
        r.patient_name = names.get(a.patient_id)
        out.append(r)
    return out


@router.post(
    "/patients/{patient_id}/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_appointment(
    patient_id: uuid.UUID,
    payload: AppointmentCreate,
    member: CurrentMember = Depends(get_current_member),
    session: AsyncSession = Depends(get_db),
) -> Appointment:
    patient = await _owned_patient(session, member, patient_id)
    # A consulta fica com o médico do paciente (a recepção agenda pelo profissional
    # responsável, não por si mesma).
    appt = Appointment(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=patient.doctor_id,
        scheduled_at=payload.scheduled_at,
        kind=payload.kind,
        location=payload.location,
        notes=payload.notes,
    )
    session.add(appt)
    await session.flush()
    # Confirmação ao agendar (se o médico do paciente não desligou). Falha de envio
    # não impede o agendamento — dá para reenviar pela Agenda.
    patient_doctor = await session.get(Doctor, patient.doctor_id)
    if prefs_of(patient_doctor).send_appointment_confirmation:
        try:
            await send_confirmation(session, appt, patient)
        except Exception:  # noqa: BLE001 — envio é best-effort
            pass
    return appt


@router.post("/appointments/{appointment_id}/confirmation", response_model=AppointmentRead)
async def send_appointment_confirmation(
    appointment_id: uuid.UUID,
    member: CurrentMember = Depends(get_current_member),
    session: AsyncSession = Depends(get_db),
) -> Appointment:
    """Envia (ou reenvia) a mensagem de confirmação da consulta ao paciente."""
    appt = await _owned_appointment(session, member, appointment_id)
    await send_confirmation(session, appt)
    return appt


@router.get("/patients/{patient_id}/appointments", response_model=list[AppointmentRead])
async def list_patient_appointments(
    patient_id: uuid.UUID,
    member: CurrentMember = Depends(get_current_member),
    session: AsyncSession = Depends(get_db),
) -> list[AppointmentRead]:
    await _owned_patient(session, member, patient_id)
    result = await session.execute(
        select(Appointment)
        .where(Appointment.patient_id == patient_id)
        .order_by(Appointment.scheduled_at.desc())
    )
    return await _with_names(session, list(result.scalars().all()))


@router.get("/appointments/upcoming", response_model=list[AppointmentRead])
async def upcoming_appointments(
    limit: int = Query(50, ge=1, le=200),
    member: CurrentMember = Depends(get_current_member),
    session: AsyncSession = Depends(get_db),
) -> list[AppointmentRead]:
    """Próximas consultas (agendadas/confirmadas), da mais próxima. Médico vê as
    suas; dono/recepção veem as da clínica (agenda compartilhada)."""
    stmt = scope_query(select(Appointment), Appointment, member).where(
        Appointment.status.in_(_OPEN),
        Appointment.scheduled_at >= datetime.now(timezone.utc),
    ).order_by(Appointment.scheduled_at).limit(limit)
    result = await session.execute(stmt)
    return await _with_names(session, list(result.scalars().all()))


@router.get("/appointments/patient-directory", response_model=list[PatientDirectoryItem])
async def patient_directory(
    member: CurrentMember = Depends(get_current_member),
    session: AsyncSession = Depends(get_db),
) -> list[PatientDirectoryItem]:
    """Lista mínima (id + nome) de pacientes para agendar pela Agenda — inclusive
    para a recepção, sem expor dado clínico. Escopo por papel."""
    rows = list(
        (
            await session.execute(
                select(Patient).where(
                    patient_visible_clause(member), Patient.is_active.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    items = [PatientDirectoryItem(id=p.id, name=p.name) for p in rows]
    items.sort(key=lambda i: i.name.lower())
    return items


@router.get("/appointments/range", response_model=list[AppointmentRead])
async def appointments_in_range(
    start: datetime = Query(..., description="Início (inclusive), ISO 8601"),
    end: datetime = Query(..., description="Fim (exclusivo), ISO 8601"),
    member: CurrentMember = Depends(get_current_member),
    session: AsyncSession = Depends(get_db),
) -> list[AppointmentRead]:
    """Consultas no período [start, end) — para o calendário (inclui concluídas/
    canceladas). Escopo por papel, como em /upcoming."""
    stmt = scope_query(select(Appointment), Appointment, member).where(
        Appointment.scheduled_at >= start,
        Appointment.scheduled_at < end,
    ).order_by(Appointment.scheduled_at)
    result = await session.execute(stmt)
    return await _with_names(session, list(result.scalars().all()))


@router.patch("/appointments/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    member: CurrentMember = Depends(get_current_member),
    session: AsyncSession = Depends(get_db),
) -> Appointment:
    appt = await _owned_appointment(session, member, appointment_id)
    changes = payload.model_dump(exclude_unset=True)
    rescheduled = "scheduled_at" in changes and changes["scheduled_at"] != appt.scheduled_at
    was_completed = appt.status is AppointmentStatus.COMPLETED
    for field, value in changes.items():
        setattr(appt, field, value)
    # Ao remarcar (novo horário), reenvia o lembrete e encerra o pedido pendente.
    if rescheduled:
        appt.reminder_sent_at = None
        appt.reschedule_requested_at = None
        appt.reschedule_note = None
        if appt.status is AppointmentStatus.CONFIRMED:
            appt.status = AppointmentStatus.SCHEDULED  # novo horário volta a "agendada"
    # Ao marcar como realizada, gera o lançamento financeiro (idempotente).
    if appt.status is AppointmentStatus.COMPLETED and not was_completed:
        patient = await session.get(Patient, appt.patient_id)
        if patient is not None:
            await generate_for_appointment(session, appt, patient)
    return appt
