"""Escalas clínicas (PHQ-9, GAD-7): catálogo, solicitação (médico) e resposta (paciente)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor, get_current_patient
from app.clinical.scales import SCALES, Scale, get_scale, score_scale
from app.db.session import get_db
from app.models.alert import Alert
from app.models.doctor import Doctor
from app.models.enums import AlertUrgency, RiskLevel
from app.models.patient import Patient
from app.models.scale_entry import ScaleEntry
from app.schemas.scale import (
    ScaleBandOut,
    ScaleDef,
    ScaleEntryRead,
    ScalePending,
    ScaleRequestIn,
    ScaleSubmitIn,
    ScaleSubmitResult,
)
from app.services.notifications import dispatch_alert, doctor_notification_contacts

router = APIRouter(tags=["scales"])

_SAFETY = (
    "Se você está com pensamentos de se ferir ou de que não vale a pena viver, "
    "procure ajuda agora: ligue 188 (CVV, 24h) ou vá a uma emergência. "
    "Seu médico foi avisado."
)


def _def(scale: Scale) -> ScaleDef:
    return ScaleDef(
        code=scale.code,
        name=scale.name,
        description=scale.description,
        period=scale.period,
        items=list(scale.items),
        options=list(scale.options),
        bands=[ScaleBandOut(min=b.min, max=b.max, label=b.label, level=b.level) for b in scale.bands],
        max_score=scale.max_score,
        flag_item=scale.flag_item,
    )


def _read(entry: ScaleEntry) -> ScaleEntryRead:
    scale = get_scale(entry.scale_code)
    return ScaleEntryRead(
        id=entry.id,
        scale_code=entry.scale_code,
        scale_name=scale.name if scale else entry.scale_code,
        status=entry.status,
        score=entry.score,
        severity=entry.severity,
        level=entry.level,
        flagged=entry.flagged,
        requested_at=entry.requested_at,
        completed_at=entry.completed_at,
    )


async def _owned_patient(session: AsyncSession, doctor: Doctor, patient_id: uuid.UUID) -> Patient:
    patient = await session.get(Patient, patient_id)
    if patient is None or patient.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente não encontrado.")
    return patient


# ---- Catálogo (médico) ----
@router.get("/scales", response_model=list[ScaleDef])
async def list_scales(_: Doctor = Depends(get_current_doctor)) -> list[ScaleDef]:
    return [_def(s) for s in SCALES.values()]


# ---- Aplicações de um paciente (médico) ----
@router.get("/patients/{patient_id}/scales", response_model=list[ScaleEntryRead])
async def patient_scales(
    patient_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[ScaleEntryRead]:
    await _owned_patient(session, doctor, patient_id)
    rows = list(
        (
            await session.execute(
                select(ScaleEntry)
                .where(ScaleEntry.patient_id == patient_id)
                .order_by(ScaleEntry.requested_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_read(r) for r in rows]


@router.post(
    "/patients/{patient_id}/scales", response_model=ScaleEntryRead,
    status_code=status.HTTP_201_CREATED,
)
async def request_scale(
    patient_id: uuid.UUID,
    payload: ScaleRequestIn,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> ScaleEntryRead:
    patient = await _owned_patient(session, doctor, patient_id)
    if get_scale(payload.scale_code) is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escala inválida.")
    entry = ScaleEntry(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        scale_code=payload.scale_code,
        status="pending",
        requested_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.flush()
    return _read(entry)


@router.delete("/scales/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scale(
    entry_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> None:
    entry = await session.get(ScaleEntry, entry_id)
    if entry is None or entry.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada.")
    if entry.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Só é possível cancelar uma pendente."
        )
    await session.delete(entry)


# ---- Paciente ----
@router.get("/patient/scales", response_model=list[ScalePending])
async def my_pending_scales(
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> list[ScalePending]:
    rows = list(
        (
            await session.execute(
                select(ScaleEntry)
                .where(ScaleEntry.patient_id == patient.id, ScaleEntry.status == "pending")
                .order_by(ScaleEntry.requested_at)
            )
        )
        .scalars()
        .all()
    )
    out: list[ScalePending] = []
    for r in rows:
        scale = get_scale(r.scale_code)
        if scale is not None:
            out.append(ScalePending(id=r.id, scale=_def(scale)))
    return out


@router.post("/patient/scales/{entry_id}", response_model=ScaleSubmitResult)
async def submit_scale(
    entry_id: uuid.UUID,
    payload: ScaleSubmitIn,
    patient: Patient = Depends(get_current_patient),
    session: AsyncSession = Depends(get_db),
) -> ScaleSubmitResult:
    entry = await session.get(ScaleEntry, entry_id)
    if entry is None or entry.patient_id != patient.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Questionário não encontrado.")
    if entry.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este questionário já foi respondido.")
    try:
        score, severity, level, flagged = score_scale(entry.scale_code, payload.answers)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    entry.answers = list(payload.answers)
    entry.score = score
    entry.severity = severity
    entry.level = level
    entry.flagged = flagged
    entry.status = "done"
    entry.completed_at = datetime.now(timezone.utc)
    await session.flush()

    # Sinal de risco (ex.: item 9 do PHQ-9) → alerta imediato ao médico.
    if flagged:
        scale = get_scale(entry.scale_code)
        reason = f"{scale.name if scale else entry.scale_code}: {scale.flag_note if scale else 'sinal de risco'}"
        alert = Alert(
            patient_id=patient.id,
            checkin_id=None,
            level=RiskLevel.RED,
            urgency=AlertUrgency.IMMEDIATE,
            reason=reason,
            reasons_detail=[reason, f"scale:{entry.scale_code}", f"entry:{entry.id}"],
        )
        session.add(alert)
        await session.flush()
        email, phone = await doctor_notification_contacts(session, patient)
        await dispatch_alert(session, alert=alert, patient=patient, email=email, phone=phone)

    return ScaleSubmitResult(
        message="Respostas registradas. Obrigado!",
        safety=_SAFETY if flagged else None,
    )
