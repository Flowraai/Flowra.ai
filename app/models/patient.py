"""Paciente — `Paciente (id, nome, contato, médico_responsável, protocolo_ativo)`.

Autenticação do paciente é feita por token opaco (sem senha): guardamos só o hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.types import EncryptedText
from app.models.enums import RiskLevel

if TYPE_CHECKING:
    from app.models.alert import Alert
    from app.models.checkin import CheckIn
    from app.models.doctor import Doctor
    from app.models.protocol import Protocol


class Patient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "patients"

    # PII cifrada em repouso (identifica o titular do dado de saúde).
    name: Mapped[str] = mapped_column(EncryptedText, nullable=False)
    # Contato (telefone/e-mail para app/WhatsApp). Dado pessoal — cifrado sob LGPD.
    contact: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    birth_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
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

    # Token de acesso do paciente (apenas o hash é persistido). Após a ativação,
    # este passa a ser o token de SESSÃO (renovado a cada login); o token do
    # convite é de primeira entrada e deixa de valer quando a sessão é emitida.
    access_token_hash: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )

    # Login por CPF + senha. Guardamos só o HASH do CPF (LGPD — nunca o CPF em
    # claro) para autenticar/lookup, e o hash bcrypt da senha. `activated_at`
    # marca quando o paciente criou o acesso (deixou de usar só o token).
    cpf_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Recuperação de senha por código (WhatsApp/e-mail): só o hash do código e a
    # validade. Autosserviço, sem depender do médico.
    pwd_reset_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pwd_reset_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
    # LGPD-4 — consentimento ESPECÍFICO para envio de texto/áudio à IA externa
    # (finalidade distinta do consentimento geral). Sem isto, o sistema usa só o
    # analisador local, nunca manda dado do paciente a terceiros.
    ai_consent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Um CPF só pode ter uma conta ativa (índice único parcial).
    __table_args__ = (
        Index(
            "uq_patients_cpf_hash", "cpf_hash",
            unique=True, postgresql_where=text("cpf_hash IS NOT NULL"),
        ),
    )

    @property
    def ai_consent(self) -> bool:
        """Paciente consentiu com o uso de IA externa (texto/áudio a terceiros)?"""
        return self.ai_consent_at is not None

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
