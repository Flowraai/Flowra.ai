"""Schemas de alerta."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import AlertStatus, AlertUrgency, RiskLevel


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    checkin_id: uuid.UUID | None = None
    level: RiskLevel
    urgency: AlertUrgency
    reason: str
    reasons_detail: list = []
    status: AlertStatus
    created_at: datetime


class AlertStatusUpdate(BaseModel):
    status: AlertStatus
