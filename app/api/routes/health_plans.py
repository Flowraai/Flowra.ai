"""Convênios (planos de saúde do paciente): CRUD do médico.

Não confundir com /billing (assinatura do SaaS). Aqui o médico cadastra os
convênios que atende e a regra de repasse por consulta.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.health_plan import HealthPlan
from app.schemas.health_plan import (
    HealthPlanBase,
    HealthPlanCreate,
    HealthPlanRead,
    HealthPlanUpdate,
)

router = APIRouter(prefix="/health-plans", tags=["health-plans"])


async def _owned(session: AsyncSession, doctor: Doctor, plan_id: uuid.UUID) -> HealthPlan:
    plan = await session.get(HealthPlan, plan_id)
    if plan is None or plan.doctor_id != doctor.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Convênio não encontrado.")
    return plan


@router.get("", response_model=list[HealthPlanRead])
async def list_health_plans(
    include_inactive: bool = False,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> list[HealthPlan]:
    stmt = select(HealthPlan).where(HealthPlan.doctor_id == doctor.id)
    if not include_inactive:
        stmt = stmt.where(HealthPlan.active.is_(True))
    stmt = stmt.order_by(HealthPlan.name)
    return list((await session.execute(stmt)).scalars().all())


@router.post("", response_model=HealthPlanRead, status_code=status.HTTP_201_CREATED)
async def create_health_plan(
    payload: HealthPlanCreate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> HealthPlan:
    plan = HealthPlan(
        tenant_id=doctor.tenant_id,
        doctor_id=doctor.id,
        name=payload.name,
        ans_code=payload.ans_code,
        payout_type=payload.payout_type,
        payout_value_cents=payload.payout_value_cents,
        payout_percent=payload.payout_percent,
        default_consultation_cents=payload.default_consultation_cents,
    )
    session.add(plan)
    await session.flush()
    return plan


@router.patch("/{plan_id}", response_model=HealthPlanRead)
async def update_health_plan(
    plan_id: uuid.UUID,
    payload: HealthPlanUpdate,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> HealthPlan:
    plan = await _owned(session, doctor, plan_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(plan, field, value)
    # Revalida a regra de repasse no estado final (fixed × percentage).
    try:
        HealthPlanBase.model_validate(
            {
                "name": plan.name,
                "ans_code": plan.ans_code,
                "payout_type": plan.payout_type,
                "payout_value_cents": plan.payout_value_cents,
                "payout_percent": plan.payout_percent,
                "default_consultation_cents": plan.default_consultation_cents,
            }
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Regra de repasse incompleta para o tipo escolhido.",
        ) from exc
    return plan


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_health_plan(
    plan_id: uuid.UUID,
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Inativa o convênio (soft-delete): preserva o vínculo histórico dos pacientes."""
    plan = await _owned(session, doctor, plan_id)
    plan.active = False
