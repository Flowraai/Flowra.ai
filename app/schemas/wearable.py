"""Schemas de vestíveis (dispositivo do paciente)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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
