"""Equipe de cuidado — profissionais que atendem um paciente.

Um paciente pode ser acompanhado por vários profissionais (psiquiatra + psicólogo
+ nutricionista). Cada linha vincula um paciente a um médico da mesma clínica.
O médico responsável original (patient.doctor_id) também entra como membro (com
is_primary=True) no backfill/cadastro.

Acesso: estar na equipe permite ao profissional ver o paciente e cuidar da SUA
parte (seus registros). Os registros clínicos seguem por autor (doctor_id).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class CareTeamMember(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "care_team"
    __table_args__ = (
        UniqueConstraint("patient_id", "doctor_id", name="uq_care_team_patient_doctor"),
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
        index=True, nullable=False,
    )
    # O responsável original do paciente (patient.doctor_id) entra como primário.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
