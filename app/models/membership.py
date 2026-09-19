"""Membership — vínculo de um usuário a um tenant (clínica) com um papel.

Base da virada "conta por médico" -> "conta da clínica": um tenant passa a ter
vários usuários (dono, médicos, recepção, financeiro). Contas solo continuam
como um tenant de uma pessoa (um único membership OWNER).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import ClinicRole


class Membership(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (
        # Um usuário tem no máximo um papel por clínica.
        UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    role: Mapped[ClinicRole] = mapped_column(
        Enum(ClinicRole, name="clinic_role"), nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Permissão por usuário: recepção enxerga o financeiro (a receber/repasses)?
    # O dono liga/desliga por pessoa. Ignorado para papéis que já veem o financeiro
    # por padrão (owner/finance) ou só o próprio (doctor).
    can_view_finance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
