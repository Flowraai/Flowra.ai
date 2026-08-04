"""Anexo (foto/arquivo/áudio) enviado no chat ou no check-in.

Os bytes ficam no backend de armazenamento (`app.services.storage`); aqui ficam
os metadados e o vínculo com o tenant/paciente, que governam o acesso ao download
(LGPD — arquivos clínicos são sensíveis, não bastam chaves não-adivinháveis).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Attachment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "attachments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    # Todo anexo pertence ao contexto de cuidado de um paciente (governa o acesso).
    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("patients.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    # Quem enviou: "patient:<id>" ou "doctor:<id>" (auditoria).
    uploaded_by: Mapped[str] = mapped_column(String(64), nullable=False)

    storage_key: Mapped[str] = mapped_column(String(128), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
