"""Schemas de receita."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrescriptionStatus


class PrescriptionItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dose: str = Field(min_length=1, max_length=120)
    instructions: str | None = None


class PrescriptionCreate(BaseModel):
    items: list[PrescriptionItem] = Field(min_length=1)
    notes: str | None = None


class PrescriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    items: list
    notes: str | None = None
    status: PrescriptionStatus
    external_id: str | None = None
    pdf_url: str | None = None
    issued_at: datetime | None = None
    created_at: datetime
