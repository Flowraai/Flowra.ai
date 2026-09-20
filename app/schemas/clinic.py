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
    clinic_share_percent: int = 0   # rateio: % das consultas que fica com a clínica
    is_self: bool = False


class MemberUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(doctor|reception)$")
    is_active: bool | None = None
    can_view_finance: bool | None = None
    clinic_share_percent: int | None = Field(default=None, ge=0, le=100)


class MemberDoctorRead(BaseModel):
    """Cadastro profissional de um médico, visto/editado pelo dono."""

    membership_id: uuid.UUID
    doctor_id: uuid.UUID
    email: str
    name: str
    specialty: str
    clinic: str | None = None
    council_id: str | None = None          # registro no conselho (ex.: CRM)
    notification_email: str | None = None
    notification_phone: str | None = None
    clinic_share_percent: int = 0


class MemberDoctorUpdate(BaseModel):
    """Campos do cadastro do médico que o dono pode alterar. Chave PIX e credenciais
    de receita/WhatsApp ficam com o próprio médico (não editáveis aqui)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    specialty: str | None = Field(default=None, max_length=120)
    clinic: str | None = Field(default=None, max_length=255)
    council_id: str | None = Field(default=None, max_length=60)
    notification_email: EmailStr | None = None
    notification_phone: str | None = Field(default=None, max_length=30)


class RiskCounts(BaseModel):
    green: int = 0
    yellow: int = 0
    orange: int = 0
    red: int = 0


class DoctorStat(BaseModel):
    """Comparativo por médico para o painel do gestor."""

    doctor_id: uuid.UUID
    name: str
    patients: int = 0
    appointments_completed: int = 0
    received_cents: int = 0        # líquido do médico
    to_receive_cents: int = 0
    clinic_cents: int = 0          # fatia da clínica gerada por este médico (recebida)


class ClinicDashboard(BaseModel):
    period_start: datetime
    period_end: datetime
    patients_total: int = 0
    doctors_total: int = 0
    risk: RiskCounts
    attention_count: int = 0
    appointments_upcoming: int = 0
    appointments_completed: int = 0
    appointments_cancelled: int = 0
    received_cents: int = 0
    to_receive_cents: int = 0
    clinic_received_cents: int = 0      # fatia da clínica recebida no período
    clinic_to_receive_cents: int = 0
    doctors: list[DoctorStat] = Field(default_factory=list)
