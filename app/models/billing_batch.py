"""Lote de faturamento de convênio (guia/remessa).

Agrupa as consultas de um convênio para cobrança. Ao criar o lote, as cobranças
entram como "billed" (faturado); depois o médico concilia cada uma como recebida
ou glosada. É específico do fluxo de convênio — particular não usa lote.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class BillingBatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "billing_batches"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    health_plan_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("health_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Rótulo livre (competência/guia), ex.: "2026-09".
    reference: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # "open" (em conciliação) | "closed" (encerrado).
    status: Mapped[str] = mapped_column(String(12), default="open", nullable=False)
