"""Schemas das escalas clínicas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScaleBandOut(BaseModel):
    min: int
    max: int
    label: str
    level: str


class ScaleDef(BaseModel):
    code: str
    name: str
    description: str
    period: str
    items: list[str]
    options: list[str]
    bands: list[ScaleBandOut]
    max_score: int
    flag_item: int | None = None


class ScaleRequestIn(BaseModel):
    scale_code: str


class ScaleSubmitIn(BaseModel):
    answers: list[int] = Field(min_length=1, max_length=30)


class ScaleEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scale_code: str
    scale_name: str
    status: str
    score: int | None = None
    severity: str | None = None
    level: str | None = None
    flagged: bool = False
    requested_at: datetime
    completed_at: datetime | None = None


class ScalePending(BaseModel):
    """Uma escala a responder pelo paciente (com a definição para renderizar)."""

    id: uuid.UUID
    scale: ScaleDef


class ScaleSubmitResult(BaseModel):
    message: str
    safety: str | None = None  # orientação de segurança quando há sinal de risco
