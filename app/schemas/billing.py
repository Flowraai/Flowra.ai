"""Schemas de planos e assinatura."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import SubscriptionStatus

_CYCLES = {"monthly", "yearly"}


class PlanBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    price_cents: int = Field(ge=0, description="Preço em centavos (R$ 149,90 = 14990)")
    cycle: str = "monthly"
    patient_limit: int | None = Field(default=None, ge=1)
    trial_days: int = Field(default=0, ge=0, le=365)
    active: bool = True
    sort_order: int = 0

    @field_validator("cycle")
    @classmethod
    def _valid_cycle(cls, value: str) -> str:
        value = value.lower()
        if value not in _CYCLES:
            raise ValueError("cycle deve ser 'monthly' ou 'yearly'")
        return value


class PlanCreate(PlanBase):
    pass


class PlanUpdate(BaseModel):
    """Todos os campos opcionais — o admin ajusta o que quiser."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    cycle: str | None = None
    patient_limit: int | None = Field(default=None, ge=1)
    trial_days: int | None = Field(default=None, ge=0, le=365)
    active: bool | None = None
    sort_order: int | None = None

    @field_validator("cycle")
    @classmethod
    def _valid_cycle(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.lower()
        if value not in _CYCLES:
            raise ValueError("cycle deve ser 'monthly' ou 'yearly'")
        return value


class PlanPublic(BaseModel):
    """Plano como o médico vê na tela de assinatura."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    price_cents: int
    cycle: str
    patient_limit: int | None = None
    trial_days: int = 0


class PlanAdmin(PlanPublic):
    """Plano completo (visão do admin), incluindo inativos."""

    active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


class SubscribeRequest(BaseModel):
    plan_id: uuid.UUID
    # CPF ou CNPJ exigido pelo Asaas para criar o cliente.
    cpf_cnpj: str = Field(min_length=11, max_length=18)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("cpf_cnpj")
    @classmethod
    def _only_digits(cls, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) not in (11, 14):
            raise ValueError("CPF (11 dígitos) ou CNPJ (14 dígitos) inválido.")
        return digits


class SubscriptionOut(BaseModel):
    """Status atual da assinatura do tenant (para o painel)."""

    status: SubscriptionStatus
    plan: PlanPublic | None = None
    current_period_end: datetime | None = None
    trial_end: datetime | None = None
    card_last4: str | None = None
    # Presente enquanto o pagamento está pendente: leva ao checkout do Asaas.
    checkout_url: str | None = None


class SubscribeResponse(BaseModel):
    status: SubscriptionStatus
    # None no modo manual (já fica ativa); URL do checkout no Asaas.
    checkout_url: str | None = None
