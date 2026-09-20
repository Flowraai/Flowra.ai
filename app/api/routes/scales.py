"""Escalas clínicas (PHQ-9, GAD-7): catálogo, solicitação (médico) e resposta (paciente)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentMember, get_current_patient, require_clinical_member
from app.clinical.packs import get_pack
from app.clinical.scales import Scale, get_scale, score_scale
from app.api.patient_access import can_access_patient, can_access_resource
from app.db.session import get_db
from app.models.alert import Alert
from app.models.enums import AlertUrgency, ClinicRole, RiskLevel
from app.models.patient import Patient
from app.models.scale_entry import ScaleEntry
from app.models.scale_target import ScaleTarget
from app.schemas.scale import (
    ScaleBandOut,
    ScaleDef,
    ScaleEntryRead,
    ScalePending,
    ScaleRequestIn,
    ScaleSubmitIn,
    ScaleSubmitResult,
    ScaleTargetIn,
    ScaleTargetRead,
)
from app.services import scale_service
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
        higher_is_worse=scale.higher_is_worse,
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
        recurring_days=entry.recurring_days,
        requested_at=entry.requested_at,
        completed_at=entry.completed_at,
    )


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


# ---- Catálogo (médico) ----
@router.get("/scales", response_model=list[ScaleDef])
async def list_scales(member: CurrentMember = Depends(require_clinical_member)) -> list[ScaleDef]:
    # Catálogo da especialidade do médico (default psiquiatria: PHQ-9 + GAD-7).
    return [_def(s) for s in get_pack(member.doctor.specialty).scales()]


# ---- Aplicações de um paciente (médico) ----
@router.get("/patients/{patient_id}/scales", response_model=list[ScaleEntryRead])
async def patient_scales(
    patient_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> list[ScaleEntryRead]:
    await _owned_patient(session, member, patient_id)
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
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> ScaleEntryRead:
    patient = await _owned_patient(session, member, patient_id)
    scale = get_scale(payload.scale_code)
    if scale is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Escala inválida.")
    entry = ScaleEntry(
        tenant_id=patient.tenant_id,
        patient_id=patient.id,
        doctor_id=member.doctor.id,
        scale_code=payload.scale_code,
        status="pending",
        recurring_days=payload.recurring_days,
        requested_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.flush()
    await scale_service.notify_patient(session, patient, scale.name)
    return _read(entry)


@router.delete("/scales/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_scale(
    entry_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> None:
    entry = await session.get(ScaleEntry, entry_id)
    if not await can_access_resource(session, member, entry):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicação não encontrada.")
    if entry.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Só é possível cancelar uma pendente."
        )
    await session.delete(entry)


# ---- Metas (limiares) de escala ----
@router.get("/patients/{patient_id}/scale-targets", response_model=list[ScaleTargetRead])
async def list_scale_targets(
    patient_id: uuid.UUID,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> list[ScaleTargetRead]:
    await _owned_patient(session, member, patient_id)
    rows = list(
        (
            await session.execute(
                select(ScaleTarget).where(ScaleTarget.patient_id == patient_id)
            )
        )
        .scalars()
        .all()
    )
    return [
        ScaleTargetRead(
            scale_code=t.scale_code,
            scale_name=(get_scale(t.scale_code).name if get_scale(t.scale_code) else t.scale_code),
            target_score=t.target_score,
        )
        for t in rows
    ]


@router.put("/patients/{patient_id}/scale-targets/{scale_code}", response_model=ScaleTargetRead)
async def set_scale_target(
    patient_id: uuid.UUID,
    scale_code: str,
    payload: ScaleTargetIn,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> ScaleTargetRead:
    patient = await _owned_patient(session, member, patient_id)
    scale = get_scale(scale_code)
    if scale is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escala desconhecida.")
    if payload.target_score > scale.max_score:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"A meta deve estar entre 0 e {scale.max_score}.",
        )
    target = await session.scalar(
        select(ScaleTarget).where(
            ScaleTarget.patient_id == patient_id, ScaleTarget.scale_code == scale_code
        )
    )
    if target is None:
        target = ScaleTarget(
            tenant_id=patient.tenant_id,
            patient_id=patient_id,
            doctor_id=member.doctor.id,
            scale_code=scale_code,
            target_score=payload.target_score,
        )
        session.add(target)
    else:
        target.target_score = payload.target_score
    return ScaleTargetRead(
        scale_code=scale_code, scale_name=scale.name, target_score=payload.target_score
    )


@router.delete(
    "/patients/{patient_id}/scale-targets/{scale_code}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_scale_target(
    patient_id: uuid.UUID,
    scale_code: str,
    member: CurrentMember = Depends(require_clinical_member),
    session: AsyncSession = Depends(get_db),
) -> None:
    await _owned_patient(session, member, patient_id)
    target = await session.scalar(
        select(ScaleTarget).where(
            ScaleTarget.patient_id == patient_id, ScaleTarget.scale_code == scale_code
        )
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meta não encontrada.")
    await session.delete(target)


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
