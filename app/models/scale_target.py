"""Meta (limiar) de uma escala para um paciente — measurement-based care.

O médico define a pontuação-alvo de uma escala (ex.: PHQ-9 ≤ 9 = remissão). O
sistema compara a última pontuação com a meta e sinaliza quando o paciente está
fora dela (no card da escala e no painel "quem precisa de atenção").
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ScaleTarget(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scale_targets"
    __table_args__ = (
        UniqueConstraint("patient_id", "scale_code", name="uq_scale_target_patient_scale"),
    )

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
    scale_code: Mapped[str] = mapped_column(String(20), nullable=False)
    # Pontuação-alvo. A direção clínica (maior = pior) vem da definição da escala.
    target_score: Mapped[int] = mapped_column(Integer, nullable=False)
