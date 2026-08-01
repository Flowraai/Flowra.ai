"""Consultas/retornos (agenda). Cadastradas pelo médico, confirmadas pelo paciente."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AppointmentKind, AppointmentStatus


class Appointment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "appointments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    kind: Mapped[AppointmentKind] = mapped_column(
        Enum(AppointmentKind, name="appointment_kind"),
        default=AppointmentKind.CONSULTATION, nullable=False,
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, name="appointment_status"),
        default=AppointmentStatus.SCHEDULED, nullable=False,
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
