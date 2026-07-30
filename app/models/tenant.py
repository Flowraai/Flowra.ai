"""Tenant — a conta que agrupa médicos e pacientes (clínica ou profissional).

Fundação multi-tenant: toda entidade de domínio pertence a um tenant, permitindo
isolamento de dados e configuração por conta. Neste primeiro passo a visibilidade
segue por médico; o `tenant_id` fica assentado para os próximos módulos (config
por tenant, compartilhamento por clínica, papéis).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin
from app.models.enums import TenantKind


class Tenant(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[TenantKind] = mapped_column(
        Enum(TenantKind, name="tenant_kind"),
        default=TenantKind.SOLO,
        nullable=False,
    )
    # Configuração por tenant (limiares de risco, canais, especialidades, etc.).
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
