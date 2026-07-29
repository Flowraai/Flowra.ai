"""Schemas do médico."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    specialty: str
    clinic: str | None = None
    council_id: str | None = None


class DoctorProfile(DoctorRead):
    email: EmailStr
