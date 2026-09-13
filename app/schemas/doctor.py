"""Schemas do médico."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class MessagePrefs(BaseModel):
    """O que o médico envia automaticamente ao paciente (e como assina)."""

    send_onboarding: bool = True            # convite/link de acesso ao cadastrar
    send_medication_reminder: bool = True   # lembrete "hora do medicamento"
    send_appointment_reminder: bool = True  # lembrete de consulta (24h antes)
    send_checkin_reminder: bool = True      # lembrete diário "faça seu check-in"
    # Assinatura opcional acrescentada ao fim das mensagens (ex.: "Dra. Ana — CRM 000").
    signature: str | None = Field(default=None, max_length=120)
    # Respostas rápidas (modelos) que o médico insere no chat com um toque.
    quick_replies: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("quick_replies")
    @classmethod
    def _clean_replies(cls, v: list[str]) -> list[str]:
        return [t.strip()[:500] for t in v if isinstance(t, str) and t.strip()][:30]


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
