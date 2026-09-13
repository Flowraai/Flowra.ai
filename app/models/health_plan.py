"""Convênio de saúde (plano do PACIENTE) — não confundir com o plano de
assinatura do SaaS (`Plan`/`Subscription`, que é o médico pagando a plataforma).

Cada convênio pertence a um tenant e guarda a regra de repasse ao médico: valor
fixo por consulta OU percentual sobre um valor de referência. Pacientes sem
convênio são "particular" (health_plan_id nulo).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class HealthPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "health_plans"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    doctor_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("doctors.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Registro ANS (opcional) — só informativo no MVP.
    ans_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Regra de repasse ao médico por consulta:
    #  - "fixed":      recebe payout_value_cents por consulta.
    #  - "percentage": recebe payout_percent% de default_consultation_cents.
    payout_type: Mapped[str] = mapped_column(String(12), default="fixed", nullable=False)
    payout_value_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payout_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0–100
    # Valor de referência da consulta neste convênio (base do percentual e sugestão).
    default_consultation_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Inativar tira o convênio das listas sem apagar o histórico dos pacientes.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def payout_for(self, gross_cents: int | None = None) -> int:
        """Repasse ao médico em centavos, dado o valor cheio da consulta.

        Para "fixed", usa o valor fixo. Para "percentage", aplica sobre o valor
        informado (ou o de referência do convênio).
        """
        if self.payout_type == "percentage":
            base = gross_cents if gross_cents is not None else (self.default_consultation_cents or 0)
            return round(base * (self.payout_percent or 0) / 100)
        return self.payout_value_cents or 0
