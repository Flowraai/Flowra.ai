"""Atestados e declarações emitidos pelo médico (afastamento, comparecimento).

Guarda os dados estruturados; o documento imprimível é montado no painel. CID e
observação são dados de saúde sensíveis — cifrados em repouso (LGPD).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import EncryptedText

CERTIFICATE_KINDS = ("afastamento", "comparecimento")


class Certificate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "certificates"

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
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # afastamento | comparecimento
    days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # afastamento
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cid: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)   # sensível
    notes: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)  # sensível
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
