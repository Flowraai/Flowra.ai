"""Registro de notificação — trilha de entrega de alertas ao médico.

Cada tentativa de entrega vira uma linha (auditável): qual canal, para quem,
se foi enviada ou falhou. Compõe a exigência de auditoria (seção 9).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import NotificationChannel, NotificationStatus

if TYPE_CHECKING:
    from app.models.alert import Alert


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    alert_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("alerts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, name="notification_channel"), nullable=False
    )
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, name="notification_status"),
        default=NotificationStatus.QUEUED,
        nullable=False,
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    alert: Mapped["Alert"] = relationship()
