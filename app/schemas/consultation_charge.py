"""Schemas dos lançamentos financeiros por consulta."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ChargeStatus = Literal["pending", "received", "cancelled"]
PaymentMethod = Literal["pix", "dinheiro", "cartao", "convenio"]


class ChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    health_plan_id: uuid.UUID | None = None
    kind: str
    gross_cents: int
    doctor_cents: int
    status: str
    payment_method: str | None = None
    received_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    # Preenchidos pela rota para exibição (não são colunas).
    patient_name: str | None = None
    health_plan_name: str | None = None


class ChargeUpdate(BaseModel):
    gross_cents: int | None = Field(default=None, ge=0)
    doctor_cents: int | None = Field(default=None, ge=0)
    status: ChargeStatus | None = None
    payment_method: PaymentMethod | None = None
    notes: str | None = Field(default=None, max_length=500)


class ChargeBucket(BaseModel):
    """Totais de repasse (centavos) de um recorte (por tipo ou convênio)."""

    to_receive_cents: int = 0
    received_cents: int = 0
    count: int = 0


class ChargePlanBucket(ChargeBucket):
    health_plan_id: uuid.UUID | None = None
    name: str  # "Particular" ou o nome do convênio


class ChargeMonth(BaseModel):
    month: str  # "YYYY-MM"
    received_cents: int = 0
    pending_cents: int = 0


class ChargeSummary(BaseModel):
    to_receive_cents: int = 0
    received_cents: int = 0
    cancelled_count: int = 0
    particular: ChargeBucket
    convenio: ChargeBucket
    by_plan: list[ChargePlanBucket]
    monthly: list[ChargeMonth]
