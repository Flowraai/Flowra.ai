"""Lembretes de medicação: plano (configurado pelo médico) e tomadas (respostas).

O médico define nome/dose/horários/duração. Para cada horário devido, gera-se uma
"tomada" (MedicationIntake) que o paciente responde: ✓ tomei / ⏰ depois / ❌ não
tomei. A adesão é calculada a partir dessas respostas.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import MedicationIntakeStatus

if TYPE_CHECKING:
    pass


class MedicationPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "medication_plans"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dose: Mapped[str] = mapped_column(String(120), nullable=False)
    # Horários do dia no formato "HH:MM" (UTC), ex.: ["08:00", "22:00"].
    times: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    intakes: Mapped[list["MedicationIntake"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class MedicationIntake(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "medication_intakes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("medication_plans.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[MedicationIntakeStatus] = mapped_column(
        Enum(MedicationIntakeStatus, name="medication_intake_status"),
        default=MedicationIntakeStatus.PENDING, nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    plan: Mapped["MedicationPlan"] = relationship(back_populates="intakes")

    __table_args__ = (
        UniqueConstraint("plan_id", "scheduled_for", name="uq_intake_plan_schedule"),
    )
