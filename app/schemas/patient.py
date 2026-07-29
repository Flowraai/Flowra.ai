"""Schemas do paciente."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RiskLevel


class PatientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contact: str | None = Field(default=None, max_length=255)
    birth_date: datetime | None = None
    # Consentimento LGPD explícito é obrigatório para dado de saúde.
    consent_given: bool = Field(
        description="Consentimento LGPD explícito do paciente para monitoramento."
    )
    consent_version: str | None = Field(default=None, max_length=30)


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    contact: str | None = None
    birth_date: datetime | None = None
    doctor_id: uuid.UUID
    active_protocol_id: uuid.UUID | None = None
    current_risk: RiskLevel
    last_checkin_at: datetime | None = None
    consent_given_at: datetime | None = None
    is_active: bool
    created_at: datetime


class PatientCreated(PatientRead):
    """Resposta da criação: inclui o token do paciente exibido uma única vez."""

    access_token: str = Field(description="Token de acesso do paciente. Guarde: não é reexibido.")


class PatientPanelItem(BaseModel):
    """Item da lista priorizada do painel do médico."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    current_risk: RiskLevel
    last_checkin_at: datetime | None = None
    open_alerts: int = 0
    days_since_checkin: int | None = None
    inactive: bool = False


class PatientTokenRead(BaseModel):
    access_token: str
