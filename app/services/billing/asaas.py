"""Integração com o Asaas (gateway de cobrança).

Fluxo de cartão **sem PCI no nosso lado**: criamos o cliente e a assinatura
(billingType CREDIT_CARD) SEM enviar dados de cartão; o Asaas gera a 1ª cobrança
com uma `invoiceUrl` (página hospedada do Asaas) onde o cliente digita o cartão.
Depois, os webhooks mantêm o status em dia.

Docs: https://docs.asaas.com  (base sandbox: https://api-sandbox.asaas.com/v3).
Autenticação pelo header `access_token`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings
from app.models.enums import SubscriptionStatus
from app.services.billing.provider import CustomerInfo, SubscriptionResult

if TYPE_CHECKING:
    from app.models.plan import Plan

_CYCLE_MAP = {"monthly": "MONTHLY", "yearly": "YEARLY", "annual": "YEARLY"}


class AsaasError(RuntimeError):
    """Falha na comunicação com o Asaas (evita vazar detalhe do gateway ao cliente)."""


class AsaasBillingProvider:
    def __init__(self) -> None:
        if not settings.asaas_api_key:
            raise AsaasError("ASAAS_API_KEY não configurada.")
        self._base = settings.asaas_base_url
        self._headers = {
            "access_token": settings.asaas_api_key,
            "User-Agent": "FlowraCare",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=20, headers=self._headers) as http:
                resp = await http.request(method, f"{self._base}{path}", **kwargs)
                resp.raise_for_status()
                return resp.json() if resp.content else {}
        except httpx.HTTPError as exc:  # noqa: TRY003
            raise AsaasError(f"Erro ao falar com o Asaas: {exc}") from exc

    async def _get_or_create_customer(self, customer: CustomerInfo) -> str:
        # Reaproveita o cliente pelo CPF/CNPJ para não duplicar no Asaas.
        found = await self._request(
            "GET", "/customers", params={"cpfCnpj": customer.cpf_cnpj}
        )
        data = found.get("data") or []
        if data:
            return str(data[0]["id"])
        body: dict[str, Any] = {
            "name": customer.name,
            "email": customer.email,
            "cpfCnpj": customer.cpf_cnpj,
        }
        if customer.phone:
            body["mobilePhone"] = customer.phone
        created = await self._request("POST", "/customers", json=body)
        return str(created["id"])

    async def create_subscription(
        self, customer: CustomerInfo, plan: "Plan", external_reference: str
    ) -> SubscriptionResult:
        customer_id = await self._get_or_create_customer(customer)
        next_due = date.today() + timedelta(days=max(plan.trial_days, 0))
        body: dict[str, Any] = {
            "customer": customer_id,
            "billingType": "CREDIT_CARD",
            "value": round(plan.price_cents / 100, 2),
            "nextDueDate": next_due.isoformat(),
            "cycle": _CYCLE_MAP.get(plan.cycle.lower(), "MONTHLY"),
            "description": f"Flowra Care — {plan.name}",
            "externalReference": external_reference,
        }
        if settings.billing_checkout_return_url:
            body["callback"] = {
                "successUrl": settings.billing_checkout_return_url,
                "autoRedirect": True,
            }
        sub = await self._request("POST", "/subscriptions", json=body)
        subscription_id = str(sub["id"])

        # A URL do checkout hospedado vem na 1ª cobrança gerada pela assinatura.
        checkout_url = await self._first_invoice_url(subscription_id)

        return SubscriptionResult(
            gateway_customer_id=customer_id,
            gateway_subscription_id=subscription_id,
            checkout_url=checkout_url,
            status=SubscriptionStatus.PENDING,
            next_due_date=next_due,
        )

    async def _first_invoice_url(self, subscription_id: str) -> str | None:
        payments = await self._request("GET", f"/subscriptions/{subscription_id}/payments")
        data = payments.get("data") or []
        if data:
            return data[0].get("invoiceUrl")
        return None

    async def cancel_subscription(self, gateway_subscription_id: str) -> None:
        await self._request("DELETE", f"/subscriptions/{gateway_subscription_id}")
