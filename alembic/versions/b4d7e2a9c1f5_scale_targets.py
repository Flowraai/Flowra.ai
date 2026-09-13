"""metas (limiares) de escala por paciente

Revision ID: b4d7e2a9c1f5
Revises: a2c9e4f7b1d3
Create Date: 2026-09-13 15:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = 'b4d7e2a9c1f5'
down_revision: str | None = 'a2c9e4f7b1d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'scale_targets',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scale_code', sa.String(length=20), nullable=False),
        sa.Column('target_score', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('patient_id', 'scale_code', name='uq_scale_target_patient_scale'),
    )
    op.create_index('ix_scale_targets_tenant_id', 'scale_targets', ['tenant_id'])
    op.create_index('ix_scale_targets_patient_id', 'scale_targets', ['patient_id'])


def downgrade() -> None:
    op.drop_table('scale_targets')
