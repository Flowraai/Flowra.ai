"""equipe de cuidado (care_team) + backfill do responsável primário

Revision ID: a7d2f9c4b8e6
Revises: f6c9d3a8e2b1
Create Date: 2026-09-20 16:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a7d2f9c4b8e6'
down_revision: str | None = 'f6c9d3a8e2b1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'care_team',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('patient_id', 'doctor_id', name='uq_care_team_patient_doctor'),
    )
    op.create_index('ix_care_team_tenant_id', 'care_team', ['tenant_id'])
    op.create_index('ix_care_team_patient_id', 'care_team', ['patient_id'])
    op.create_index('ix_care_team_doctor_id', 'care_team', ['doctor_id'])

    # Backfill: o responsável atual de cada paciente vira membro primário.
    op.execute(
        """
        INSERT INTO care_team (id, tenant_id, patient_id, doctor_id, is_primary, created_at, updated_at)
        SELECT gen_random_uuid(), p.tenant_id, p.id, p.doctor_id, true, now(), now()
        FROM patients p
        ON CONFLICT (patient_id, doctor_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index('ix_care_team_doctor_id', table_name='care_team')
    op.drop_index('ix_care_team_patient_id', table_name='care_team')
    op.drop_index('ix_care_team_tenant_id', table_name='care_team')
    op.drop_table('care_team')
