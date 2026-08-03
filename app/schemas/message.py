"""Schemas de chat (mensagens)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MessageSender


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    # Anexos [{"url", "type"}] — o upload em si é um follow-up.
    attachments: list[dict] = Field(default_factory=list)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sender: MessageSender
    body: str
    attachments: list
    read_at: datetime | None = None
    created_at: datetime
