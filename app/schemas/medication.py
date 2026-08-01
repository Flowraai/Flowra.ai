"""Schemas de lembretes de medicação."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import MedicationIntakeStatus

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_times(value: list[str]) -> list[str]:
    if not value:
        raise ValueError("informe ao menos um horário")
    for item in value:
        if not isinstance(item, str) or not _HHMM.match(item):
            raise ValueError(f"horário inválido: {item!r} (use HH:MM, 24h)")
    return value


class MedicationPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dose: str = Field(min_length=1, max_length=120)
    times: list[str] = Field(description='Horários "HH:MM" (UTC), ex.: ["08:00","22:00"]')
    start_date: date
    end_date: date | None = None
    notes: str | None = None

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        return _validate_times(v)


class MedicationPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    dose: str | None = Field(default=None, min_length=1, max_length=120)
    times: list[str] | None = None
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None
    active: bool | None = None

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str] | None) -> list[str] | None:
        return _validate_times(v) if v is not None else v


class MedicationPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    name: str
    dose: str
    times: list[str]
    start_date: date
    end_date: date | None = None
    notes: str | None = None
    active: bool


class MedicationIntakeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    scheduled_for: datetime
    status: MedicationIntakeStatus
    responded_at: datetime | None = None


class MedicationDoseToday(BaseModel):
    """Dose do dia para o app: dados do remédio + a tomada correspondente."""

    intake_id: uuid.UUID
    plan_id: uuid.UUID
    name: str
    dose: str
    scheduled_for: datetime
    status: MedicationIntakeStatus


class MedicationIntakeRespond(BaseModel):
    status: MedicationIntakeStatus

    @field_validator("status")
    @classmethod
    def _not_pending(cls, v: MedicationIntakeStatus) -> MedicationIntakeStatus:
        if v is MedicationIntakeStatus.PENDING:
            raise ValueError("resposta deve ser taken, later ou missed")
        return v


class MedicationAdherence(BaseModel):
    total: int
    taken: int
    later: int
    missed: int
    pending: int
    adherence_rate: float  # taken / (respondidas), 0..1
