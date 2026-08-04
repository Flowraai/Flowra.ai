"""Chat: mensagens entre paciente e médico (e, futuramente, IA).

A thread é implícita pelo par (paciente, médico). `attachments` guarda anexos
(arquivos/fotos/áudios) como [{"url", "type"}] — o upload/armazenamento fica para
um follow-up; o campo já existe para o app.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import EncryptedText
from app.models.enums import MessageSender, MessageThread


class Message(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "messages"

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
    thread: Mapped[MessageThread] = mapped_column(
        Enum(MessageThread, name="message_thread"),
        default=MessageThread.CARE, nullable=False,
    )
    sender: Mapped[MessageSender] = mapped_column(
        Enum(MessageSender, name="message_sender"), nullable=False
    )
    # Conteúdo da conversa — cifrado em repouso (LGPD).
    body: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    attachments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
