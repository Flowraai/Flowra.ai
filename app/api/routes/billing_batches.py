"""Faturamento de convênio em lotes (guias) e conciliação (recebido/glosado).

O médico agrupa as cobranças pendentes de um convênio num lote — elas passam a
"billed" (faturado). Depois concilia cada cobrança via PATCH /charges/{id}
(received ou denied+motivo). Particular não usa lote.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.billing_batch import BillingBatch
from app.models.consultation_charge import ConsultationCharge
from app.models.doctor import Doctor
from app.models.health_plan import HealthPlan
from app.schemas.consultation_charge import (
    BatchCreate,
    BatchDetail,
    BatchRead,
    ChargeRead,
)

router = APIRouter(prefix="/billing-batches", tags=["billing-batches"])


async def _owned_batch(session: AsyncSession, doctor: Doctor, batch_id: uuid.UUID) -> BillingBatch:
    batch = await session.get(BillingBatch, batch_id)
    if batch is None or batch.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lote não encontrado.")
    return batch


async def _charges_of(session: AsyncSession, batch_id: uuid.UUID) -> list[ConsultationCharge]:
    return list(
        (
            await session.execute(
                select(ConsultationCharge)
                .where(ConsultationCharge.batch_id == batch_id)
                .order_by(ConsultationCharge.created_at)
            )
        )
        .scalars()
        .all()
    )


def _batch_read(batch: BillingBatch, charges: list[ConsultationCharge], plan_name: str | None) -> BatchRead:
    r = BatchRead.model_validate(batch)
    r.health_plan_name = plan_name
    r.charge_count = len(charges)
    r.billed_cents = sum(c.doctor_cents for c in charges if c.status == "billed")
    r.received_cents = sum(c.doctor_cents for c in charges if c.status == "received")
    r.denied_cents = sum(c.doctor_cents for c in charges if c.status == "denied")
    return r


@router.post("", response_model=BatchDetail, status_code=status.HTTP_201_CREATED)
async def create_batch(
    payload: BatchCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> BatchDetail:
    plan = await session.get(HealthPlan, payload.health_plan_id)
    if plan is None or plan.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convênio não encontrado.")

    # Seleciona as cobranças a faturar: as informadas, ou todas as pendentes do convênio.
    stmt = select(ConsultationCharge).where(
        ConsultationCharge.doctor_id == doctor.id,
        ConsultationCharge.health_plan_id == plan.id,
        ConsultationCharge.status == "pending",
    )
    if payload.charge_ids:
        stmt = stmt.where(ConsultationCharge.id.in_(payload.charge_ids))
    charges = list((await session.execute(stmt)).scalars().all())
    if not charges:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhuma cobrança pendente deste convênio para faturar.",
        )

    batch = BillingBatch(
        tenant_id=doctor.tenant_id,
        doctor_id=doctor.id,
        health_plan_id=plan.id,
        reference=payload.reference,
        status="open",
    )
    session.add(batch)
    await session.flush()
    for c in charges:
        c.batch_id = batch.id
        c.status = "billed"

    detail = BatchDetail.model_validate(_batch_read(batch, charges, plan.name))
    detail.charges = [ChargeRead.model_validate(c) for c in charges]
    return detail


@router.get("", response_model=list[BatchRead])
async def list_batches(
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[BatchRead]:
    batches = list(
        (
            await session.execute(
                select(BillingBatch)
                .where(BillingBatch.doctor_id == doctor.id)
                .order_by(BillingBatch.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    if not batches:
        return []
    plan_ids = {b.health_plan_id for b in batches}
    names = {
        pid: name
        for pid, name in (
            await session.execute(
                select(HealthPlan.id, HealthPlan.name).where(HealthPlan.id.in_(plan_ids))
            )
        ).all()
    }
    out = []
    for b in batches:
        charges = await _charges_of(session, b.id)
        out.append(_batch_read(b, charges, names.get(b.health_plan_id)))
    return out


@router.get("/{batch_id}", response_model=BatchDetail)
async def get_batch(
    batch_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> BatchDetail:
    batch = await _owned_batch(session, doctor, batch_id)
    charges = await _charges_of(session, batch_id)
    plan = await session.get(HealthPlan, batch.health_plan_id)
    detail = BatchDetail.model_validate(_batch_read(batch, charges, plan.name if plan else None))
    detail.charges = [ChargeRead.model_validate(c) for c in charges]
    return detail


@router.post("/{batch_id}/close", response_model=BatchRead)
async def close_batch(
    batch_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> BatchRead:
    batch = await _owned_batch(session, doctor, batch_id)
    batch.status = "closed"
    charges = await _charges_of(session, batch_id)
    plan = await session.get(HealthPlan, batch.health_plan_id)
    return _batch_read(batch, charges, plan.name if plan else None)
