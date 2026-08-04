"""Contrato do provedor de cobrança e a fábrica que escolhe a implementação.

Padrão igual aos outros provedores plugáveis (notificação, receita, push):
- `manual` (default): não fala com gateway nenhum. Serve para dev/testes — a
  assinatura já nasce ATIVA. Nenhum cartão é cobrado.
- `asaas`: cria cliente + assinatura no Asaas e devolve a URL do checkout
  hospedado (o cartão é digitado na página do Asaas, nunca no nosso servidor).

Contrato mínimo: criar cliente, criar assinatura, cancelar assinatura. O status
ao longo do tempo é mantido pelos webhooks (ver rotas de billing).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Protocol

from app.core.config import settings
from app.models.enums import SubscriptionStatus

if TYPE_CHECKING:
    from app.models.plan import Plan


@dataclass
class SubscriptionResult:
    """Resultado de criar uma assinatura no provedor."""

    gateway_customer_id: str | None
    gateway_subscription_id: str | None
    # URL do checkout hospedado (o cliente digita o cartão lá). None no manual.
    checkout_url: str | None
    # Status inicial: PENDING quando aguarda o 1º pagamento; ACTIVE no manual.
    status: SubscriptionStatus
    next_due_date: date | None = None


@dataclass
class CustomerInfo:
    """Dados mínimos exigidos pelo gateway para criar o cliente."""

    name: str
    email: str
    cpf_cnpj: str
    phone: str | None = None


class BillingProvider(Protocol):
    async def create_subscription(
        self, customer: CustomerInfo, plan: "Plan", external_reference: str
    ) -> SubscriptionResult: ...

    async def cancel_subscription(self, gateway_subscription_id: str) -> None: ...


class ManualBillingProvider:
    """Sem gateway. A assinatura nasce ATIVA — para dev/testes."""

    async def create_subscription(
        self, customer: CustomerInfo, plan: "Plan", external_reference: str
    ) -> SubscriptionResult:
        return SubscriptionResult(
            gateway_customer_id=None,
            gateway_subscription_id=None,
            checkout_url=None,
            status=SubscriptionStatus.ACTIVE,
        )

    async def cancel_subscription(self, gateway_subscription_id: str) -> None:
        return None


def get_billing_provider() -> BillingProvider:
    if settings.billing_provider.lower() == "asaas":
        from app.services.billing.asaas import AsaasBillingProvider

        return AsaasBillingProvider()
    return ManualBillingProvider()
