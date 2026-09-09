"""Anotações clínicas do médico: evolução, diagnóstico e outros pontos.

Texto livre do prontuário, opcionalmente vinculado a uma consulta (para anotar
"na consulta"). Conteúdo clínico é sensível — cifrado em repouso (LGPD).
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import EncryptedText

# Tipos de anotação (validados no schema). String simples evita tipo enum no banco.
NOTE_KINDS = ("note", "diagnosis", "other")


class ClinicalNote(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "clinical_notes"

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
    # Vínculo opcional com uma consulta (anotação "da consulta"). SET NULL preserva
    # a anotação se a consulta for removida.
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL"),
        index=True, nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(20), default="note", nullable=False)
    body: Mapped[str] = mapped_column(EncryptedText, nullable=False)
