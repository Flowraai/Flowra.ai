"""Receitas. A emissão com valor legal (ICP-Brasil / controlado) é delegada a um
provedor certificado (ver app/services/prescription_provider.py); aqui guardamos
a prescrição e a referência externa (id/PDF).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import PrescriptionStatus


class Prescription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "prescriptions"

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
    # Itens: [{"name", "dose", "instructions"}].
    items: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PrescriptionStatus] = mapped_column(
        Enum(PrescriptionStatus, name="prescription_status"),
        default=PrescriptionStatus.DRAFT, nullable=False,
    )
    # Referência do provedor certificado (quando emitida).
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
