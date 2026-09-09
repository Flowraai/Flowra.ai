"""Schemas de anotações clínicas (prontuário)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NoteKind = Literal["note", "diagnosis", "other"]


class NoteCreate(BaseModel):
    kind: NoteKind = "note"
    body: str = Field(min_length=1, max_length=10000)
    appointment_id: uuid.UUID | None = None


class NoteUpdate(BaseModel):
    kind: NoteKind | None = None
    body: str | None = Field(default=None, min_length=1, max_length=10000)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    appointment_id: uuid.UUID | None = None
    kind: NoteKind
    body: str
    created_at: datetime
    updated_at: datetime
