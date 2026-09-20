"""Schemas dos lançamentos financeiros por consulta."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# pending: a receber · billed: faturado (em lote, aguardando convênio)
# received: recebido · denied: glosado · cancelled: cancelado
ChargeStatus = Literal["pending", "billed", "received", "denied", "cancelled"]
PaymentMethod = Literal["pix", "dinheiro", "cartao", "convenio"]


class ChargeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    health_plan_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    kind: str
    gross_cents: int
    doctor_cents: int
    clinic_cents: int = 0
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
    # Fatia da clínica (rateio) no período — a receber e recebida.
    clinic_to_receive_cents: int = 0
    clinic_received_cents: int = 0
    denied_cents: int = 0
    cancelled_count: int = 0
    denied_count: int = 0
    particular: ChargeBucket
    convenio: ChargeBucket
    by_plan: list[ChargePlanBucket]
    monthly: list[ChargeMonth]


class PixCode(BaseModel):
    """Payload PIX "copia e cola" (BR Code) de uma cobrança particular."""

    payload: str
    amount_cents: int
    receiver: str
    city: str


class BatchCreate(BaseModel):
    health_plan_id: uuid.UUID
    reference: str | None = Field(default=None, max_length=40)
    # Cobranças a incluir. Vazio/omitido = todas as pendentes do convênio.
    charge_ids: list[uuid.UUID] | None = None


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_plan_id: uuid.UUID
    reference: str | None = None
    status: str
    created_at: datetime
    # Preenchidos pela rota.
    health_plan_name: str | None = None
    charge_count: int = 0
    billed_cents: int = 0  # ainda aguardando (billed)
    received_cents: int = 0
    denied_cents: int = 0


class BatchDetail(BatchRead):
    charges: list[ChargeRead] = Field(default_factory=list)
