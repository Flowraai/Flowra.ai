"""Schemas de check-in."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RiskLevel


class CheckInCreate(BaseModel):
    # Respostas por código de pergunta do protocolo: {"mood": 3, "crisis": "sim", ...}
    structured_responses: dict = Field(default_factory=dict)
    free_text: str | None = Field(default=None, max_length=5000)
    audio_url: str | None = Field(default=None, max_length=2000)
    # Data do check-in. None = hoje. Permite responder um dia esquecido (retroativo)
    # dentro da janela permitida. Nunca no futuro.
    for_date: date | None = None


class CalendarDay(BaseModel):
    """Um dia no calendário do paciente."""

    date: date
    checked_in: bool
    can_fill: bool          # dia passado em branco, dentro da janela -> pode responder
    is_today: bool
    mood: int | None = None  # humor daquele dia (o próprio registro), se houver


class CheckInRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    protocol_id: uuid.UUID | None = None
    structured_responses: dict
    free_text: str | None = None
    audio_url: str | None = None
    audio_transcript: str | None = None
    risk_level: RiskLevel
    risk_reasons: list = []
    category_risks: dict = {}
    created_at: datetime


class CheckInResult(BaseModel):
    """Retorno enxuto ao paciente após o check-in (sem expor detalhe clínico)."""

    id: uuid.UUID
    received_at: datetime
    message: str
