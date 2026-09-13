"""Lançamento financeiro de uma consulta (a receber / recebido).

Gerado quando a consulta é marcada como realizada. Guarda o valor cheio
(gross_cents) e o repasse ao médico (doctor_cents) — em consultório solo os dois
coincidem no particular; no convênio o repasse vem da regra do plano. Dinheiro
sempre em centavos (int). Faturamento em lote e glosas entram no Marco 4.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin

# kind: "particular" | "convenio"
# status: "pending" (a receber) | "received" (recebido) | "cancelled"
# payment_method: "pix" | "dinheiro" | "cartao" | "convenio" | None


class ConsultationCharge(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "consultation_charges"
    __table_args__ = (
        # Um lançamento por consulta (evita duplicar ao reprocessar).
        UniqueConstraint("appointment_id", name="uq_charge_appointment"),
    )

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
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Snapshot do convênio no momento (nulo = particular).
    health_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("health_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    gross_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    doctor_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="pending", nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(12), nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
