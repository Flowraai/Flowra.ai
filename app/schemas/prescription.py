"""Schemas de receita."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import PrescriptionStatus

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class PrescriptionItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dose: str = Field(min_length=1, max_length=120)
    instructions: str | None = None
    # Horários "HH:MM" para acompanhar na Medicação (lembrete + adesão). Ao EMITIR
    # a receita, cada item com horário vira um plano de medicação. Vazio = fica só
    # na receita (ex.: medicamento "se necessário", sem lembrete).
    times: list[str] = Field(default_factory=list)

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        for item in v:
            if not isinstance(item, str) or not _HHMM.match(item):
                raise ValueError(f"horário inválido: {item!r} (use HH:MM, 24h)")
        return v


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


# ---- Integração com plataforma de receita (por médico) ----
class PrescriptionProviderInfo(BaseModel):
    slug: str
    name: str
    legal_value: bool
    requires_credential: bool
    credential_label: str | None = None
    description: str
    available: bool


class PrescriptionIntegration(BaseModel):
    """Estado da integração de receita do médico (nunca devolve o segredo)."""

    provider: str
    provider_name: str
    legal_value: bool
    available: bool
    connected: bool


class PrescriptionIntegrationUpdate(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    # Credencial da conta do médico (token). Opcional: pode conectar o provedor
    # e informar o token depois. Enviada só na gravação; nunca é devolvida.
    credential: str | None = Field(default=None, max_length=2000)
