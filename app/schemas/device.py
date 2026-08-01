"""Schemas de device token (push)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeviceRegister(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    platform: Literal["ios", "android", "web"]


class DeviceTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: str
    is_active: bool


class PushTestResult(BaseModel):
    sent: int
    results: dict[str, str]
