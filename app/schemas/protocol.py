"""Schemas de protocolo (consumidos pelo app do paciente e pelo painel)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import QuestionType


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    category: str
    text: str
    type: QuestionType
    position: int
    required: bool
    options: dict | None = None


class ProtocolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    specialty: str
    version: str
    description: str | None = None
    is_active: bool
    questions: list[QuestionRead] = []
