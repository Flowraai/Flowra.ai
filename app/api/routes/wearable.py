"""Dispositivos vestíveis: conexão do paciente e leitura pelo médico."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor, get_current_patient
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.patient import Patient
from app.schemas.wearable import (
    WearableConnectResult,
    WearableDay,
    WearableSamplesIn,
    WearableSummary,
)
from app.services import wearable_service
from app.services.wearable_provider import PROVIDERS, DailySample, active_provider_info

router = APIRouter(tags=["wearable"])


_MOBILE_NAMES = {
    "health_connect": "Health Connect (Android)",
    "healthkit": "Apple Saúde",
    "mobile": "App de celular",
}


def _provider_name(provider: str | None) -> str | None:
    if not provider:
        return None
    if provider in PROVIDERS:
        return PROVIDERS[provider].name
    return _MOBILE_NAMES.get(provider, provider)


def _to_summary(data: dict) -> WearableSummary:
    info = active_provider_info()
    latest = data.get("latest")
    return WearableSummary(
        connected=data["connected"],
        provider=data.get("provider"),
        provider_name=_provider_name(data.get("provider")),
        requires_oauth=info.requires_oauth,
        last_sync_at=data.get("last_sync_at"),
        latest=WearableDay.model_validate(latest) if latest is not None else None,
        avg_sleep_minutes=data.get("avg_sleep_minutes"),
        avg_resting_hr=data.get("avg_resting_hr"),
        avg_hrv_ms=data.get("avg_hrv_ms"),
        avg_steps=data.get("avg_steps"),
        days=[WearableDay.model_validate(d) for d in data.get("days", [])],
    )


# ---- Paciente ----
@router.get("/patient/wearable", response_model=WearableSummary)
async def my_wearable(
    days: int = Query(14, ge=1, le=90),
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> WearableSummary:
    return _to_summary(await wearable_service.summary(session, patient, days))


@router.post("/patient/wearable/connect", response_model=WearableConnectResult)
async def connect_wearable(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> WearableConnectResult:
    conn, oauth_url = await wearable_service.connect(session, patient)
    return WearableConnectResult(connected=oauth_url is None, connect_url=oauth_url)


@router.post("/patient/wearable/sync", response_model=WearableSummary)
async def sync_wearable(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> WearableSummary:
    if await wearable_service.get_connection(session, patient) is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Nenhum dispositivo conectado."
        )
    await wearable_service.sync_patient(session, patient)
    return _to_summary(await wearable_service.summary(session, patient))


@router.post("/patient/wearable/samples", response_model=WearableSummary)
async def push_samples(
    payload: WearableSamplesIn,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> WearableSummary:
    """Ingestão do app de celular: recebe os dias lidos do HealthKit/Health Connect
    e grava o resumo diário (upsert). Cria a conexão na primeira vez."""
    conn = await wearable_service.ensure_connection(session, patient, payload.source)
    samples = [
        DailySample(
            day=d.day,
            sleep_minutes=d.sleep_minutes,
            resting_hr=d.resting_hr,
            hrv_ms=d.hrv_ms,
            steps=d.steps,
        )
        for d in payload.days
    ]
    await wearable_service.upsert_samples(session, patient, payload.source, samples)
    conn.last_sync_at = datetime.now(timezone.utc)
    await session.flush()
    return _to_summary(await wearable_service.summary(session, patient))


@router.post("/patient/wearable/disconnect", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_wearable(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> None:
    await wearable_service.disconnect(session, patient)


# ---- Médico ----
@router.get("/patients/{patient_id}/wearable", response_model=WearableSummary)
async def patient_wearable(
    patient_id: uuid.UUID,
    days: int = Query(14, ge=1, le=90),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> WearableSummary:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return _to_summary(await wearable_service.summary(session, patient, days))
