"""Convite para entrar numa clínica (tenant) com um papel.

O dono convida por e-mail; o convidado abre o link e define a senha, virando um
Membership do tenant (e um Doctor, se o papel for médico). O token é guardado
cifrado (hash), como o de redefinição de senha — o valor cru vai só no link.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ClinicRole


class Invitation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "invitations"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    role: Mapped[ClinicRole] = mapped_column(
        # Reaproveita o tipo clinic_role já criado pela migração de memberships.
        PgEnum(ClinicRole, name="clinic_role", create_type=False), nullable=False,
    )
    can_view_finance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
