"""Schemas do convênio (plano de saúde do paciente)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PayoutType = Literal["fixed", "percentage"]


class HealthPlanBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    ans_code: str | None = Field(default=None, max_length=20)
    payout_type: PayoutType = "fixed"
    payout_value_cents: int | None = Field(default=None, ge=0)
    payout_percent: int | None = Field(default=None, ge=0, le=100)
    default_consultation_cents: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _check_rule(self) -> "HealthPlanBase":
        if self.payout_type == "fixed":
            if self.payout_value_cents is None:
                raise ValueError("Informe o valor de repasse (payout_value_cents) para repasse fixo.")
        else:  # percentage
            if self.payout_percent is None:
                raise ValueError("Informe o percentual (payout_percent) para repasse percentual.")
            if self.default_consultation_cents is None:
                raise ValueError(
                    "Informe o valor de referência da consulta para repasse percentual."
                )
        return self


class HealthPlanCreate(HealthPlanBase):
    pass


class HealthPlanUpdate(BaseModel):
    """Atualização parcial. A regra é revalidada no endpoint com o estado final."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    ans_code: str | None = Field(default=None, max_length=20)
    payout_type: PayoutType | None = None
    payout_value_cents: int | None = Field(default=None, ge=0)
    payout_percent: int | None = Field(default=None, ge=0, le=100)
    default_consultation_cents: int | None = Field(default=None, ge=0)
    active: bool | None = None


class HealthPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    ans_code: str | None = None
    payout_type: str
    payout_value_cents: int | None = None
    payout_percent: int | None = None
    default_consultation_cents: int | None = None
    active: bool
