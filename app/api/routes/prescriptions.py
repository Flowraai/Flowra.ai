"""Rotas de receita (lado do médico): rascunho, emissão, renovação, cancelamento."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, require_clinical_member
from app.api.patient_access import can_access_patient, can_access_resource
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import ClinicRole, PrescriptionStatus
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.schemas.prescription import (
    PrescriptionCreate,
    PrescriptionIntegration,
    PrescriptionIntegrationUpdate,
    PrescriptionProviderInfo,
    PrescriptionRead,
)
from app.services.medication_service import create_plans_from_prescription
from app.services.notifications import send_plain
from app.services.prescription_provider import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    get_prescription_provider,
)
from app.services.push_service import push_to_patient

router = APIRouter(tags=["prescriptions"])


def _integration_state(doctor: Doctor) -> PrescriptionIntegration:
    slug = (doctor.prescription_provider or DEFAULT_PROVIDER).lower()
    info = PROVIDERS.get(slug, PROVIDERS[DEFAULT_PROVIDER])
    connected = (not info.requires_credential) or bool(doctor.prescription_credential)
    return PrescriptionIntegration(
        provider=info.slug,
        provider_name=info.name,
        legal_value=info.legal_value,
        available=info.available,
        connected=connected,
    )


@router.get("/prescriptions/providers", response_model=list[PrescriptionProviderInfo])
async def list_providers(_: CurrentMember = Depends(require_clinical_member)) -> list[PrescriptionProviderInfo]:
    """Plataformas de receita disponíveis para o médico escolher."""
    return [PrescriptionProviderInfo(**vars(info)) for info in PROVIDERS.values()]


@router.get("/prescriptions/integration", response_model=PrescriptionIntegration)
async def get_integration(
    member: CurrentMember = Depends(require_clinical_member),
) -> PrescriptionIntegration:
    return _integration_state(member.doctor)


@router.put("/prescriptions/integration", response_model=PrescriptionIntegration)
async def set_integration(
    payload: PrescriptionIntegrationUpdate,
    member: CurrentMember = Depends(require_clinical_member),
) -> PrescriptionIntegration:
    slug = payload.provider.lower()
    if slug not in PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Provedor de receita inválido."
        )
    member.doctor.prescription_provider = slug
    # Só troca a credencial quando enviada (permite salvar o provedor sem reenviar o token).
    if payload.credential is not None:
        member.doctor.prescription_credential = payload.credential.strip() or None
    if slug == DEFAULT_PROVIDER:
        member.doctor.prescription_credential = None
    return _integration_state(member.doctor)


@router.delete("/prescriptions/integration", response_model=PrescriptionIntegration)
async def clear_integration(
    member: CurrentMember = Depends(require_clinical_member),
) -> PrescriptionIntegration:
    member.doctor.prescription_provider = None
    member.doctor.prescription_credential = None
    return _integration_state(member.doctor)


def _scope_ok(row, member: CurrentMember) -> bool:
    """No escopo do membro? Médico vê o que é dele; dono vê a clínica inteira."""
    if member.role is ClinicRole.DOCTOR and member.doctor is not None:
        return row.doctor_id == member.doctor.id
    return row.tenant_id == member.tenant_id


async def _owned_patient(
    session: AsyncSession, member: CurrentMember, patient_id: uuid.UUID
) -> Patient:
    patient = await session.get(Patient, patient_id)
    if not await can_access_patient(session, member, patient):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


async def _owned_prescription(
    session: AsyncSession, member: CurrentMember, prescription_id: uuid.UUID
) -> Prescription:
    presc = await session.get(Prescription, prescription_id)
    if not await can_access_resource(session, member, presc):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receita não encontrada.")
    return presc


@router.post(
    "/patients/{patient_id}/prescriptions",
    response_model=PrescriptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    patient_id: uuid.UUID,
    payload: PrescriptionCreate,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Prescription:
    patient = await _owned_patient(session, member, patient_id)
    presc = Prescription(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=member.doctor.id,
        items=[i.model_dump() for i in payload.items],
        notes=payload.notes,
    )
    session.add(presc)
    await session.flush()
    return presc


@router.get("/patients/{patient_id}/prescriptions", response_model=list[PrescriptionRead])
async def list_prescriptions(
    patient_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> list[Prescription]:
    await _owned_patient(session, member, patient_id)
    result = await session.execute(
        select(Prescription)
        .where(Prescription.patient_id == patient_id)
        .order_by(Prescription.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/prescriptions/{prescription_id}", response_model=PrescriptionRead)
async def get_prescription(
    prescription_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Prescription:
    return await _owned_prescription(session, member, prescription_id)


@router.post("/prescriptions/{prescription_id}/issue", response_model=PrescriptionRead)
async def issue_prescription(
    prescription_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Prescription:
    """Emite a receita pelo provedor configurado e avisa o paciente."""
    presc = await _owned_prescription(session, member, prescription_id)
    if presc.status is not PrescriptionStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Somente rascunhos podem ser emitidos."
        )
    try:
        external_id, pdf_url = await get_prescription_provider(member.doctor).issue(presc)
    except (RuntimeError, NotImplementedError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Provedor de receita indisponível: {exc}",
        ) from exc

    presc.status = PrescriptionStatus.ISSUED
    presc.external_id = external_id
    presc.pdf_url = pdf_url
    presc.issued_at = datetime.now(timezone.utc)

    # Medicamentos com horário viram acompanhamento na Medicação (lembrete + adesão).
    await create_plans_from_prescription(session, presc)

    subject = "[Flowra Care] Nova receita"
    body = "Seu médico emitiu uma nova receita. Abra o app para acessá-la."
    patient = await session.get(Patient, presc.patient_id)
    if patient is not None and patient.contact:
        await send_plain(target=patient.contact, subject=subject, body=body)
    await push_to_patient(session, presc.patient_id, subject, body)
    return presc


@router.post("/prescriptions/{prescription_id}/renew", response_model=PrescriptionRead,
             status_code=status.HTTP_201_CREATED)
async def renew_prescription(
    prescription_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Prescription:
    """Cria um novo rascunho a partir de uma receita existente (renovação)."""
    original = await _owned_prescription(session, member, prescription_id)
    renewed = Prescription(
        tenant_id=original.tenant_id,
        patient_id=original.patient_id,
        doctor_id=original.doctor_id,
        items=original.items,
        notes=original.notes,
    )
    session.add(renewed)
    await session.flush()
    return renewed


@router.post("/prescriptions/{prescription_id}/cancel", response_model=PrescriptionRead)
async def cancel_prescription(
    prescription_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> Prescription:
    presc = await _owned_prescription(session, member, prescription_id)
    presc.status = PrescriptionStatus.CANCELLED
    return presc
