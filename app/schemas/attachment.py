"""Schemas de anexos."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content_type: str
    size_bytes: int
    filename: str | None = None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def url(self) -> str:
        """URL de download (referenciável em mensagens/check-ins)."""
        return f"/api/v1/attachments/{self.id}"
