"""Schemas do médico."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    specialty: str
    clinic: str | None = None
    council_id: str | None = None
    notification_email: str | None = None
    notification_phone: str | None = None


class DoctorProfile(DoctorRead):
    email: EmailStr


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=120)
    clinic: str | None = Field(default=None, max_length=255)
    council_id: str | None = Field(default=None, max_length=60)
    notification_email: EmailStr | None = None
    notification_phone: str | None = Field(default=None, max_length=30)
