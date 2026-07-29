"""Protocolo — `Protocolo (id, especialidade, lista_de_perguntas)`.

Modelado como Protocol + ProtocolQuestion (data-driven) para que o "Motor de
Protocolos" leia as perguntas por código. O protocolo psiquiátrico do MVP é
pré-definido e populado via seed (app/scripts/seed_protocol.py).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import QuestionType

if TYPE_CHECKING:
    pass


class Protocol(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "protocols"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), default="psiquiatria", nullable=False)
    version: Mapped[str] = mapped_column(String(30), default="1.0", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    questions: Mapped[list["ProtocolQuestion"]] = relationship(
        back_populates="protocol",
        cascade="all, delete-orphan",
        order_by="ProtocolQuestion.position",
    )

    __table_args__ = (UniqueConstraint("specialty", "version", name="uq_protocol_specialty_version"),)


class ProtocolQuestion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "protocol_questions"

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("protocols.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Código estável usado pelo motor de risco (ex.: "mood", "crisis").
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)  # Humor, Sono, ...
    text: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Metadados da pergunta: escala (min/max), opções de choice, unidade, etc.
    options: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    protocol: Mapped["Protocol"] = relationship(back_populates="questions")

    __table_args__ = (UniqueConstraint("protocol_id", "code", name="uq_question_protocol_code"),)
