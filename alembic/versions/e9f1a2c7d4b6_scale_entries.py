"""escalas clínicas (PHQ-9, GAD-7): aplicações e pontuação

Revision ID: e9f1a2c7d4b6
Revises: d3b8a1c6e9f4
Create Date: 2026-09-12 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = 'e9f1a2c7d4b6'
down_revision: str | None = 'd3b8a1c6e9f4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'scale_entries',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scale_code', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='pending'),
        sa.Column('answers', JSONB(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('severity', sa.String(length=40), nullable=True),
        sa.Column('level', sa.String(length=10), nullable=True),
        sa.Column('flagged', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('requested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scale_entries_tenant_id', 'scale_entries', ['tenant_id'])
    op.create_index('ix_scale_entries_patient_id', 'scale_entries', ['patient_id'])


def downgrade() -> None:
    op.drop_table('scale_entries')
