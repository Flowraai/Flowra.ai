"""Médico — `Médico (id, nome, especialidade, clínica)`."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class Doctor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "doctors"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), default="psiquiatria", nullable=False)
    clinic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Registro no conselho (ex.: CRM) — relevante para rastreabilidade clínica.
    council_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    # Destino das notificações de alerta (se vazio, usa o e-mail de login).
    notification_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Telefone (E.164) para notificações via WhatsApp.
    notification_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    user: Mapped["User"] = relationship(back_populates="doctor")
    patients: Mapped[list["Patient"]] = relationship(
        back_populates="doctor",
        cascade="all, delete-orphan",
    )
