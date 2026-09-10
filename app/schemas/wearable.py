"""Schemas de vestíveis (dispositivo do paciente)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WearableDayIn(BaseModel):
    """Um dia de dados enviado pelo app de celular (HealthKit/Health Connect)."""

    day: date
    sleep_minutes: int | None = Field(default=None, ge=0, le=1440)
    resting_hr: int | None = Field(default=None, ge=20, le=250)
    hrv_ms: int | None = Field(default=None, ge=0, le=500)
    steps: int | None = Field(default=None, ge=0, le=200000)


class WearableSamplesIn(BaseModel):
    """Lote de dias enviado pelo app. `source` diz a origem no celular."""

    source: Literal["health_connect", "healthkit", "mobile"] = "mobile"
    days: list[WearableDayIn] = Field(min_length=1, max_length=120)


class WearableDay(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    sleep_minutes: int | None = None
    resting_hr: int | None = None
    hrv_ms: int | None = None
    steps: int | None = None


class WearableSummary(BaseModel):
    connected: bool
    provider: str | None = None
    provider_name: str | None = None
    requires_oauth: bool = False
    last_sync_at: datetime | None = None
    latest: WearableDay | None = None
    avg_sleep_minutes: int | None = None
    avg_resting_hr: int | None = None
    avg_hrv_ms: int | None = None
    avg_steps: int | None = None
    days: list[WearableDay] = []


class WearableConnectResult(BaseModel):
    connected: bool
    # Para provedores OAuth (Terra/Fitbit): URL para o paciente autorizar. None = já conectou.
    connect_url: str | None = None
