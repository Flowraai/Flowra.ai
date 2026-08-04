"""Área do administrador da plataforma: gestão de planos de assinatura.

Restrita a ADMIN_EMAILS. O admin cria/edita/ativa planos que o médico vê na
tela de assinatura. Ajuste de preço vale para novas assinaturas.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.billing import PlanAdmin, PlanCreate, PlanUpdate

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/plans", response_model=list[PlanAdmin])
async def list_plans(session: AsyncSession = Depends(get_db)) -> list[Plan]:
    result = await session.execute(select(Plan).order_by(Plan.sort_order, Plan.price_cents))
    return list(result.scalars().all())


@router.post("/plans", response_model=PlanAdmin, status_code=status.HTTP_201_CREATED)
async def create_plan(payload: PlanCreate, session: AsyncSession = Depends(get_db)) -> Plan:
    plan = Plan(**payload.model_dump())
    session.add(plan)
    await session.flush()
    return plan


@router.patch("/plans/{plan_id}", response_model=PlanAdmin)
async def update_plan(
    plan_id: uuid.UUID, payload: PlanUpdate, session: AsyncSession = Depends(get_db)
) -> Plan:
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    return plan


@router.delete("/plans/{plan_id}", status_code=status.HTTP_200_OK)
async def delete_plan(
    plan_id: uuid.UUID,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
) -> dict:
    plan = await session.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano não encontrado.")
    # Se já houver assinaturas apontando para o plano, só desativa (preserva histórico).
    in_use = await session.execute(
        select(Subscription.id).where(Subscription.plan_id == plan_id).limit(1)
    )
    if in_use.first() is not None:
        plan.active = False
        return {"deactivated": True, "reason": "Plano em uso — desativado em vez de excluído."}
    await session.delete(plan)
    return {"deleted": True}
