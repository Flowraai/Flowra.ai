"""Assinatura do médico: listar planos, assinar (checkout), status e webhook."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_doctor, get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.doctor import Doctor
from app.models.enums import SubscriptionStatus
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.billing import (
    PlanPublic,
    SubscribeRequest,
    SubscribeResponse,
    SubscriptionOut,
)
from app.services.billing import get_billing_provider
from app.services.billing.provider import CustomerInfo

logger = logging.getLogger("flowra_care.billing")

router = APIRouter(prefix="/billing", tags=["billing"])


def _cycle_delta(cycle: str) -> timedelta:
    return timedelta(days=366) if cycle.lower() in ("yearly", "annual") else timedelta(days=31)


async def _tenant_subscription(session: AsyncSession, tenant_id) -> Subscription | None:
    result = await session.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


@router.get("/plans", response_model=list[PlanPublic])
async def list_active_plans(
    _: Doctor = Depends(get_current_doctor), session: AsyncSession = Depends(get_db)
) -> list[Plan]:
    result = await session.execute(
        select(Plan).where(Plan.active.is_(True)).order_by(Plan.sort_order, Plan.price_cents)
    )
    return list(result.scalars().all())


@router.get("/subscription", response_model=SubscriptionOut)
async def my_subscription(
    doctor: Doctor = Depends(get_current_doctor), session: AsyncSession = Depends(get_db)
) -> SubscriptionOut:
    sub = await _tenant_subscription(session, doctor.tenant_id)
    if sub is None:
        return SubscriptionOut(status=SubscriptionStatus.PENDING, plan=None)
    plan = await session.get(Plan, sub.plan_id)
    return SubscriptionOut(
        status=sub.status,
        plan=PlanPublic.model_validate(plan) if plan else None,
        current_period_end=sub.current_period_end,
        trial_end=sub.trial_end,
        card_last4=sub.card_last4,
    )


@router.post("/subscribe", response_model=SubscribeResponse, status_code=status.HTTP_201_CREATED)
async def subscribe(
    payload: SubscribeRequest,
    user: User = Depends(get_current_user),
    doctor: Doctor = Depends(get_current_doctor),
    session: AsyncSession = Depends(get_db),
) -> SubscribeResponse:
    plan = await session.get(Plan, payload.plan_id)
    if plan is None or not plan.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plano indisponível.")

    sub = await _tenant_subscription(session, doctor.tenant_id)
    if sub is not None and sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe uma assinatura ativa."
        )

    provider = get_billing_provider()
    customer = CustomerInfo(
        name=doctor.name,
        email=user.email,
        cpf_cnpj=payload.cpf_cnpj,
        phone=payload.phone,
    )
    try:
        result = await provider.create_subscription(
            customer, plan, external_reference=str(doctor.tenant_id)
        )
    except Exception:  # noqa: BLE001 — não vaza detalhe do gateway ao cliente
        logger.exception("Falha ao criar assinatura no gateway")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível iniciar a assinatura. Tente novamente.",
        )

    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=plan.trial_days) if plan.trial_days > 0 else None
    # No modo manual a assinatura já nasce ativa; libera o período do ciclo.
    period_end = now + _cycle_delta(plan.cycle) if result.status is SubscriptionStatus.ACTIVE else None

    if sub is None:
        sub = Subscription(tenant_id=doctor.tenant_id, plan_id=plan.id)
        session.add(sub)
    sub.plan_id = plan.id
    sub.status = result.status
    sub.gateway_customer_id = result.gateway_customer_id
    sub.gateway_subscription_id = result.gateway_subscription_id
    sub.trial_end = trial_end
    sub.current_period_end = period_end
    sub.canceled_at = None

    return SubscribeResponse(status=result.status, checkout_url=result.checkout_url)


@router.post("/cancel", response_model=SubscriptionOut)
async def cancel(
    doctor: Doctor = Depends(get_current_doctor), session: AsyncSession = Depends(get_db)
) -> SubscriptionOut:
    sub = await _tenant_subscription(session, doctor.tenant_id)
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sem assinatura.")
    if sub.gateway_subscription_id:
        try:
            await get_billing_provider().cancel_subscription(sub.gateway_subscription_id)
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao cancelar assinatura no gateway")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Não foi possível cancelar agora. Tente novamente.",
            )
    sub.status = SubscriptionStatus.CANCELED
    sub.canceled_at = datetime.now(timezone.utc)
    plan = await session.get(Plan, sub.plan_id)
    return SubscriptionOut(
        status=sub.status,
        plan=PlanPublic.model_validate(plan) if plan else None,
        current_period_end=sub.current_period_end,
        trial_end=sub.trial_end,
    )


# Eventos do Asaas -> transição de status da assinatura.
_ACTIVATE_EVENTS = {"PAYMENT_CONFIRMED", "PAYMENT_RECEIVED", "PAYMENT_RECEIVED_IN_CASH"}
_OVERDUE_EVENTS = {"PAYMENT_OVERDUE"}
_CANCEL_EVENTS = {
    "PAYMENT_DELETED",
    "PAYMENT_REFUNDED",
    "PAYMENT_CHARGEBACK_REQUESTED",
    "SUBSCRIPTION_DELETED",
}


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def asaas_webhook(request: Request, session: AsyncSession = Depends(get_db)) -> dict:
    """Recebe eventos do Asaas e sincroniza o status da assinatura.

    Autenticado pelo header `asaas-access-token` (mesmo valor de ASAAS_WEBHOOK_TOKEN).
    """
    expected = settings.asaas_webhook_token
    if not expected or request.headers.get("asaas-access-token") != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook não autorizado.")

    body = await request.json()
    event = body.get("event")
    payment = body.get("payment") or {}
    gateway_sub_id = payment.get("subscription")
    if not gateway_sub_id:
        # Alguns eventos (ex.: de assinatura) trazem o id em outro lugar.
        gateway_sub_id = (body.get("subscription") or {}).get("id")
    if not gateway_sub_id:
        return {"ignored": True}

    result = await session.execute(
        select(Subscription).where(Subscription.gateway_subscription_id == str(gateway_sub_id))
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return {"ignored": True}

    now = datetime.now(timezone.utc)
    if event in _ACTIVATE_EVENTS:
        plan = await session.get(Plan, sub.plan_id)
        sub.status = SubscriptionStatus.ACTIVE
        sub.current_period_end = now + _cycle_delta(plan.cycle if plan else "monthly")
        last4 = payment.get("creditCard", {}).get("creditCardNumber")
        if last4:
            sub.card_last4 = str(last4)[-4:]
    elif event in _OVERDUE_EVENTS:
        sub.status = SubscriptionStatus.OVERDUE
    elif event in _CANCEL_EVENTS:
        sub.status = SubscriptionStatus.CANCELED
        sub.canceled_at = now

    return {"ok": True}
