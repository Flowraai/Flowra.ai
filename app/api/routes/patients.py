"""Rotas do médico para gestão de pacientes e painel priorizado."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.core.security import (
    generate_patient_token,
    hash_patient_token,
)
from app.db.session import get_db
from app.models.alert import Alert
from app.models.checkin import CheckIn
from app.models.doctor import Doctor
from app.models.enums import AlertStatus, AuditAction
from app.models.patient import Patient
from app.models.protocol import Protocol
from app.schemas.alert import AlertRead
from app.schemas.checkin import CheckInRead
from app.schemas.patient import (
    PatientCreate,
    PatientCreated,
    PatientExport,
    PatientOnboarding,
    PatientPanelItem,
    PatientRead,
    PatientTokenRead,
    PatientUpdate,
)
from app.services import audit
from app.services.inactivity_service import days_since_checkin, is_inactive, scan_inactivity
from app.services.onboarding_service import build_onboarding_link, send_onboarding

router = APIRouter(prefix="/patients", tags=["patients"])


async def _active_psychiatry_protocol(session: AsyncSession) -> Protocol | None:
    result = await session.execute(
        select(Protocol)
        .where(Protocol.specialty == "psiquiatria", Protocol.is_active.is_(True))
        .order_by(Protocol.created_at.desc())
    )
    return result.scalars().first()


async def _get_owned_patient(
    session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID
) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


@router.post("", response_model=PatientCreated, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> PatientCreated:
    # LGPD: consentimento explícito é pré-requisito para dado de saúde.
    if not payload.consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Consentimento LGPD explícito é obrigatório para cadastrar o paciente.",
        )

    protocol = await _active_psychiatry_protocol(session)
    token = generate_patient_token()

    patient = Patient(
        name=payload.name,
        contact=payload.contact,
        birth_date=payload.birth_date,
        doctor_id=doctor.id,
        active_protocol_id=protocol.id if protocol else None,
        access_token_hash=hash_patient_token(token),
        consent_given_at=datetime.now(timezone.utc),
        consent_version=payload.consent_version,
    )
    session.add(patient)
    await session.flush()

    await audit.record(
        session,
        action=AuditAction.PATIENT_CREATED,
        actor=f"doctor:{doctor.id}",
        entity_type="patient",
        entity_id=patient.id,
        metadata={"consent_version": payload.consent_version},
    )

    # Entrega o acesso ao paciente automaticamente (best-effort; não bloqueia o cadastro).
    await send_onboarding(session, patient, token)

    base = PatientRead.model_validate(patient).model_dump()
    return PatientCreated(**base, access_token=token)


@router.get("", response_model=list[PatientPanelItem])
async def list_patients(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[PatientPanelItem]:
    """Painel do médico: pacientes ordenados por risco (maior primeiro)."""
    result = await session.execute(
        select(Patient).where(Patient.doctor_id == doctor.id, Patient.is_active.is_(True))
    )
    patients = list(result.scalars().all())

    # Contagem de alertas em aberto (não resolvidos) por paciente.
    counts_result = await session.execute(
        select(Alert.patient_id, func.count(Alert.id))
        .where(
            Alert.patient_id.in_([p.id for p in patients] or [uuid.uuid4()]),
            Alert.status != AlertStatus.RESOLVED,
        )
        .group_by(Alert.patient_id)
    )
    open_counts = {pid: count for pid, count in counts_result.all()}

    now = datetime.now(timezone.utc)
    items = [
        PatientPanelItem(
            id=p.id,
            name=p.name,
            current_risk=p.current_risk,
            last_checkin_at=p.last_checkin_at,
            open_alerts=open_counts.get(p.id, 0),
            days_since_checkin=days_since_checkin(p, now),
            inactive=is_inactive(p, now),
        )
        for p in patients
    ]
    # Ordena por severidade de risco (desc) e, em empate, check-in mais antigo primeiro.
    items.sort(
        key=lambda i: (
            -i.current_risk.order,
            i.last_checkin_at or datetime.min.replace(tzinfo=timezone.utc),
        )
    )
    return items[offset : offset + limit]


@router.get("/{patient_id}", response_model=PatientRead)
async def get_patient(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Patient:
    return await _get_owned_patient(session, doctor, patient_id)


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(
    patient_id: uuid.UUID,
    payload: PatientUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Patient:
    """Edita dados do paciente e ativa/desativa (is_active)."""
    patient = await _get_owned_patient(session, doctor, patient_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("name") is not None:
        patient.name = data["name"]
    if "contact" in data:
        patient.contact = data["contact"]
    if "birth_date" in data:
        patient.birth_date = data["birth_date"]
    if data.get("is_active") is not None:
        patient.is_active = data["is_active"]

    await audit.record(
        session,
        action=AuditAction.PATIENT_UPDATED,
        actor=f"doctor:{doctor.id}",
        entity_type="patient",
        entity_id=patient.id,
        metadata={"fields": sorted(data.keys())},
    )
    return patient


@router.get("/{patient_id}/export", response_model=PatientExport)
async def export_patient_data(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> PatientExport:
    """Portabilidade LGPD: exporta todos os dados do paciente (paciente + histórico)."""
    patient = await _get_owned_patient(session, doctor, patient_id)
    checkins = (
        await session.execute(
            select(CheckIn).where(CheckIn.patient_id == patient_id).order_by(CheckIn.created_at)
        )
    ).scalars().all()
    alerts = (
        await session.execute(
            select(Alert).where(Alert.patient_id == patient_id).order_by(Alert.created_at)
        )
    ).scalars().all()

    await audit.record(
        session,
        action=AuditAction.PATIENT_EXPORTED,
        actor=f"doctor:{doctor.id}",
        entity_type="patient",
        entity_id=patient_id,
    )
    return PatientExport(
        exported_at=datetime.now(timezone.utc),
        patient=PatientRead.model_validate(patient),
        checkins=[CheckInRead.model_validate(c) for c in checkins],
        alerts=[AlertRead.model_validate(a) for a in alerts],
    )


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Response:
    """Direito de eliminação (LGPD): apaga o paciente e seus dados de saúde.

    Cascata no banco remove check-ins, alertas e notificações. O log de auditoria
    é preservado (referencia apenas IDs — proteção jurídica da plataforma/médico).
    """
    patient = await _get_owned_patient(session, doctor, patient_id)
    await session.execute(delete(Patient).where(Patient.id == patient.id))
    await audit.record(
        session,
        action=AuditAction.PATIENT_DELETED,
        actor=f"doctor:{doctor.id}",
        entity_type="patient",
        entity_id=patient_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{patient_id}/checkins", response_model=list[CheckInRead])
async def patient_checkins(
    patient_id: uuid.UUID,
    limit: int = Query(30, ge=1, le=200),
    offset: int = Query(0, ge=0),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[CheckIn]:
    await _get_owned_patient(session, doctor, patient_id)
    result = await session.execute(
        select(CheckIn)
        .where(CheckIn.patient_id == patient_id)
        .order_by(CheckIn.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post("/{patient_id}/rotate-token", response_model=PatientTokenRead)
async def rotate_patient_token(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> PatientTokenRead:
    patient = await _get_owned_patient(session, doctor, patient_id)
    token = generate_patient_token()
    patient.access_token_hash = hash_patient_token(token)
    await audit.record(
        session,
        action=AuditAction.PATIENT_TOKEN_ROTATED,
        actor=f"doctor:{doctor.id}",
        entity_type="patient",
        entity_id=patient.id,
    )
    return PatientTokenRead(access_token=token)


@router.post("/{patient_id}/resend-onboarding", response_model=PatientOnboarding)
async def resend_onboarding(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> PatientOnboarding:
    """Gera um novo token de acesso e reenvia o link de onboarding ao paciente."""
    patient = await _get_owned_patient(session, doctor, patient_id)
    token = generate_patient_token()
    patient.access_token_hash = hash_patient_token(token)
    await audit.record(
        session,
        action=AuditAction.PATIENT_TOKEN_ROTATED,
        actor=f"doctor:{doctor.id}",
        entity_type="patient",
        entity_id=patient.id,
    )
    sent = await send_onboarding(session, patient, token)
    return PatientOnboarding(
        access_token=token, onboarding_link=build_onboarding_link(token), sent=sent
    )


@router.post("/scan-inactivity", response_model=list[AlertRead])
async def scan_patient_inactivity(
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[Alert]:
    """Gera alertas de não-adesão para os pacientes deste médico sem check-in recente."""
    return await scan_inactivity(session, doctor_id=doctor.id)
