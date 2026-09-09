"""Schemas do médico."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class MessagePrefs(BaseModel):
    """O que o médico envia automaticamente ao paciente (e como assina)."""

    send_onboarding: bool = True            # convite/link de acesso ao cadastrar
    send_medication_reminder: bool = True   # lembrete "hora do medicamento"
    send_appointment_reminder: bool = True  # lembrete de consulta (24h antes)
    # Assinatura opcional acrescentada ao fim das mensagens (ex.: "Dra. Ana — CRM 000").
    signature: str | None = Field(default=None, max_length=120)


class DoctorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    specialty: str
    clinic: str | None = None
    council_id: str | None = None
    notification_email: str | None = None
    notification_phone: str | None = None


class DoctorProfile(DoctorRead):
    email: EmailStr
    tenant_name: str | None = None
    is_admin: bool = False
    message_prefs: MessagePrefs = Field(default_factory=MessagePrefs)


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=120)
    clinic: str | None = Field(default=None, max_length=255)
    council_id: str | None = Field(default=None, max_length=60)
    notification_email: EmailStr | None = None
    notification_phone: str | None = Field(default=None, max_length=30)
    message_prefs: MessagePrefs | None = None
