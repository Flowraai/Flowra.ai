"""CheckIn — `CheckIn (id, paciente_id, data, respostas_estruturadas,
texto_livre, áudio_url, risco_calculado)`.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import EncryptedText
from app.models.enums import RiskLevel

if TYPE_CHECKING:
    from app.models.patient import Patient


class CheckIn(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "checkins"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    protocol_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("protocols.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Respostas estruturadas por código de pergunta: {"mood": 3, "crisis": true, ...}
    structured_responses: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Texto livre ("Quer contar mais alguma coisa sobre hoje?") e/ou áudio.
    # Conteúdo clínico — cifrado em repouso (LGPD).
    free_text: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Transcrição do áudio (quando a transcrição está habilitada); alimenta o risco.
    audio_transcript: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)

    # Resultado do motor de risco.
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level"),
        default=RiskLevel.GREEN,
        nullable=False,
    )
    # Motivos determinísticos + sinais da IA que justificaram o risco (auditável).
    risk_reasons: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Risco por categoria: {"Humor": "orange", "Sono": "green", ...}
    category_risks: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="checkins")
