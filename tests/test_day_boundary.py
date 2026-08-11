"""Fronteira do dia (um check-in por dia) ancorada no fuso configurado, não em UTC."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from app.api.routes.patient_app import _start_of_day_utc
from app.core.config import settings


def test_start_of_day_is_local_midnight_expressed_in_utc():
    start = _start_of_day_utc()
    # Aware (comparável com created_at, que é UTC).
    assert start.tzinfo is not None
    # Convertido de volta ao fuso configurado, cai na meia-noite local — não na
    # meia-noite UTC (que, no BR/UTC-3, adiantaria a virada do dia em 3h).
    local = start.astimezone(ZoneInfo(settings.checkin_timezone))
    assert (local.hour, local.minute, local.second, local.microsecond) == (0, 0, 0, 0)
