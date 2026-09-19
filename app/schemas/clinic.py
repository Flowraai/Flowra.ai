"""Schemas de equipe e convites da clínica."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# owner é o dono; convites são só para doctor/reception (o dono já existe).
InvitableRole = str  # validado na rota (doctor|reception)


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(doctor|reception)$")
    can_view_finance: bool = False


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    can_view_finance: bool
    expires_at: datetime
    accepted_at: datetime | None = None
    created_at: datetime


class InvitationAccept(BaseModel):
    token: str
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class MemberRead(BaseModel):
    """Um integrante da equipe (para a tela de gestão)."""

    id: uuid.UUID          # id do membership
    user_id: uuid.UUID
    email: str
    name: str | None = None
    role: str
    is_active: bool
    can_view_finance: bool
    is_self: bool = False


class MemberUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(doctor|reception)$")
    is_active: bool | None = None
    can_view_finance: bool | None = None
