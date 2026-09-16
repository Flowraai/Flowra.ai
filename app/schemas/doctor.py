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
    send_appointment_confirmation: bool = True  # confirma a consulta ao agendar
    # Modelo da mensagem de confirmação. Placeholders: {paciente} {tipo} {data}
    # {hora} {local}. Vazio = usa o texto padrão do sistema.
    appointment_confirmation_template: str | None = Field(default=None, max_length=600)
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
    pix_key: str | None = None
    pix_city: str | None = None


class SpecialtyOption(BaseModel):
    """Opção de especialidade (pacote clínico) para o seletor do médico."""

    key: str
    label: str


class CareInfo(BaseModel):
    """Resumo do pacote clínico da especialidade (o front liga/desliga módulos)."""

    specialty: str
    label: str
    features: dict[str, bool] = Field(default_factory=dict)


class DoctorProfile(DoctorRead):
    email: EmailStr
    tenant_name: str | None = None
    is_admin: bool = False
    message_prefs: MessagePrefs = Field(default_factory=MessagePrefs)
    care: CareInfo | None = None


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=120)
    clinic: str | None = Field(default=None, max_length=255)
    council_id: str | None = Field(default=None, max_length=60)
    notification_email: EmailStr | None = None
    notification_phone: str | None = Field(default=None, max_length=30)
    pix_key: str | None = Field(default=None, max_length=140)
    pix_city: str | None = Field(default=None, max_length=60)
    message_prefs: MessagePrefs | None = None
