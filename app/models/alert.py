"""Alerta — `Alerta (id, paciente_id, nível, motivo, status, data)`."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AlertStatus, AlertUrgency, RiskLevel

if TYPE_CHECKING:
    from app.models.patient import Patient


class Alert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "alerts"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    checkin_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("checkins.id", ondelete="SET NULL"),
        nullable=True,
    )

    level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, name="risk_level"), nullable=False)
    urgency: Mapped[AlertUrgency] = mapped_column(
        Enum(AlertUrgency, name="alert_urgency"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reasons_detail: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status"),
        default=AlertStatus.PENDING,
        nullable=False,
        index=True,
    )

    patient: Mapped["Patient"] = relationship(back_populates="alerts")
