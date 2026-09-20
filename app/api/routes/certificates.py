"""Atestados e declarações (lado do médico)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, require_clinical_member
from app.db.session import get_db
from app.models.certificate import Certificate
from app.models.enums import ClinicRole
from app.models.patient import Patient
from app.schemas.certificate import CertificateCreate, CertificateRead

router = APIRouter(tags=["certificates"])


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
    "/patients/{patient_id}/certificates", response_model=CertificateRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_certificate(
    patient_id: uuid.UUID,
    payload: CertificateCreate,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Certificate:
    patient = await _owned_patient(session, member, patient_id)
    if payload.kind == "afastamento" and not payload.days:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe os dias de afastamento.",
        )
    cert = Certificate(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=member.doctor.id,
        kind=payload.kind,
        days=payload.days,
        start_date=payload.start_date,
        cid=(payload.cid or "").strip() or None,
        notes=(payload.notes or "").strip() or None,
        issued_at=datetime.now(timezone.utc),
    )
    session.add(cert)
    await session.flush()
    return cert


@router.get("/patients/{patient_id}/certificates", response_model=list[CertificateRead])
async def list_certificates(
    patient_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> list[Certificate]:
    await _owned_patient(session, member, patient_id)
    result = await session.execute(
        select(Certificate)
        .where(Certificate.patient_id == patient_id)
        .order_by(Certificate.issued_at.desc())
    )
    return list(result.scalars().all())


@router.get("/certificates/{certificate_id}", response_model=CertificateRead)
async def get_certificate(
    certificate_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Certificate:
    cert = await session.get(Certificate, certificate_id)
    if cert is None or not _scope_ok(cert, member):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Atestado não encontrado.")
    return cert
