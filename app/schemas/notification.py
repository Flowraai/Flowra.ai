"""Schemas de notificação."""

from __future__ import annotations

from pydantic import BaseModel


class NotificationTestResult(BaseModel):
    target: str
    results: dict[str, str]  # canal -> "sent" | "failed: <motivo>"
