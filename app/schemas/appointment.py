"""Schemas de consultas/retornos."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AppointmentKind, AppointmentStatus


class AppointmentCreate(BaseModel):
    scheduled_at: datetime
    kind: AppointmentKind = AppointmentKind.CONSULTATION
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    scheduled_at: datetime | None = None
    kind: AppointmentKind | None = None
    status: AppointmentStatus | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    doctor_id: uuid.UUID
    scheduled_at: datetime
    kind: AppointmentKind
    status: AppointmentStatus
    location: str | None = None
    notes: str | None = None
