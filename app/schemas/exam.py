"""Schemas de exames."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ExamStatus


class ExamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class ExamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: ExamStatus | None = None
    result_url: str | None = None
    notes: str | None = None


class ExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    name: str
    status: ExamStatus
    result_url: str | None = None
    notes: str | None = None
    available_at: datetime | None = None
    created_at: datetime
