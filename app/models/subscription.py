"""Assinatura de um tenant (a conta) a um plano.

O acesso ao painel clínico depende do status desta assinatura, que é mantido em
sincronia com o gateway (Asaas) pelos webhooks. Uma assinatura por tenant.

Nada de dado de cartão aqui: o número do cartão é digitado na página hospedada
do Asaas (invoiceUrl) e nunca passa pelo nosso servidor. Guardamos apenas os IDs
do gateway e, opcionalmente, os 4 últimos dígitos para exibição.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import SubscriptionStatus


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.PENDING,
        nullable=False,
    )
    # IDs no gateway (Asaas). Nulos enquanto o provedor for "manual" (dev).
    gateway_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway_subscription_id: Mapped[str | None] = mapped_column(
        String(64), index=True, nullable=True
    )
    # Últimos 4 dígitos do cartão (só para exibição; nunca o número completo).
    card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    # Fim do período pago (libera o acesso até esta data).
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["Plan"] = relationship()


from app.models.plan import Plan  # noqa: E402  (evita import circular no type hint)
