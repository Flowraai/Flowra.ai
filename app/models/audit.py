"""Log de auditoria — exigência de compliance (seção 9 do planejamento).

Registra todos os check-ins, cálculos de risco, alertas gerados e ações tomadas,
como proteção jurídica para a plataforma e para o médico.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import AuditAction


class AuditLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action"), index=True, nullable=False
    )
    # Ator: "doctor:<id>", "patient:<id>" ou "system".
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
