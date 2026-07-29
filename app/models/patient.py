"""Paciente — `Paciente (id, nome, contato, médico_responsável, protocolo_ativo)`.

Autenticação do paciente é feita por token opaco (sem senha): guardamos só o hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import RiskLevel

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.checkin import CheckIn
    from app.models.doctor import Doctor
    from app.models.protocol import Protocol


class Patient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "patients"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Contato (telefone/e-mail para app/WhatsApp). Dado pessoal — tratar sob LGPD.
    contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    active_protocol_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("protocols.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Token de acesso do paciente (apenas o hash é persistido).
    access_token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )

    # Índice de risco atual (denormalizado para ordenar o painel do médico).
    current_risk: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level"),
        default=RiskLevel.GREEN,
        nullable=False,
    )
    last_checkin_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Consentimento LGPD (dado de saúde é categoria sensível).
    consent_given_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consent_version: Mapped[str | None] = mapped_column(String(30), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    doctor: Mapped["Doctor"] = relationship(back_populates="patients")
    active_protocol: Mapped["Protocol | None"] = relationship()
    checkins: Mapped[list["CheckIn"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="CheckIn.created_at.desc()",
    )
    alerts: Mapped[list["Alert"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
    )
