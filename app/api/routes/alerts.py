"""Rotas de alertas do médico."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.alert import Alert
from app.models.doctor import Doctor
from app.models.enums import AlertStatus, AuditAction
from app.models.patient import Patient
from app.schemas.alert import AlertRead, AlertStatusUpdate
from app.services import audit

router = APIRouter(prefix="/alerts", tags=["alerts"])


async def _get_owned_alert(
    session: AsyncSession, doctor: Doctor, alert_id: uuid.UUID
) -> Alert:
    result = await session.execute(
        select(Alert)
        .join(Patient, Alert.patient_id == Patient.id)
        .where(Alert.id == alert_id, Patient.doctor_id == doctor.id)
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerta não encontrado.")
    return alert


@router.get("", response_model=list[AlertRead])
async def list_alerts(
    status_filter: AlertStatus | None = None,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[Alert]:
    query = (
        select(Alert)
        .join(Patient, Alert.patient_id == Patient.id)
        .where(Patient.doctor_id == doctor.id)
    )
    if status_filter is not None:
        query = query.where(Alert.status == status_filter)
    query = query.order_by(Alert.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


@router.patch("/{alert_id}", response_model=AlertRead)
async def update_alert_status(
    alert_id: uuid.UUID,
    payload: AlertStatusUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> Alert:
    alert = await _get_owned_alert(session, doctor, alert_id)
    previous = alert.status
    alert.status = payload.status
    await audit.record(
        session,
        action=AuditAction.ALERT_STATUS_CHANGED,
        actor=f"doctor:{doctor.id}",
        entity_type="alert",
        entity_id=alert.id,
        metadata={"from": previous.value, "to": payload.status.value},
    )
    return alert
