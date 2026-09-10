"""Dispositivos vestíveis (relógio/pulseira): conexão do paciente e dados diários.

Arquitetura agnóstica de fornecedor: `provider` diz de onde vieram os dados
(demo, e futuramente terra/fitbit/…). Guardamos um resumo DIÁRIO por paciente
(sono, FC de repouso, HRV, passos) — não a série bruta — o que basta para o
acompanhamento e minimiza dado sensível (LGPD).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import EncryptedText


class WearableConnection(UUIDMixin, TimestampMixin, Base):
    """Vínculo do paciente com um dispositivo/fornecedor (um por paciente)."""

    __tablename__ = "wearable_connections"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        unique=True, index=True, nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    # Id opaco do usuário no fornecedor (ex.: user_id da Terra) — não é PII em si e
    # precisa ser consultável nos webhooks; fica em claro, indexado. A credencial
    # (tokens OAuth) permanece cifrada em repouso.
    external_user_id: Mapped[str | None] = mapped_column(Text, index=True, nullable=True)
    credential: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WearableDaily(UUIDMixin, TimestampMixin, Base):
    """Resumo diário de um paciente (uma linha por dia)."""

    __tablename__ = "wearable_daily"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    sleep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resting_hr: Mapped[int | None] = mapped_column(Integer, nullable=True)   # bpm
    hrv_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)       # ms
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("patient_id", "day", name="uq_wearable_daily_patient_day"),
    )
