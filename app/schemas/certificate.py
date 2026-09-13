"""Schemas de atestados e declarações."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CertKind = Literal["afastamento", "comparecimento"]


class CertificateCreate(BaseModel):
    kind: CertKind
    days: int | None = Field(default=None, ge=1, le=365)
    start_date: date | None = None
    cid: str | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)


class CertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    kind: CertKind
    days: int | None = None
    start_date: date | None = None
    cid: str | None = None
    notes: str | None = None
    issued_at: datetime
    created_at: datetime
