"""dispositivos vestíveis: conexão e resumo diário

Revision ID: a7c4e1f9b2d6
Revises: f6b3d2e9a4c1
Create Date: 2026-09-09 20:15:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = 'a7c4e1f9b2d6'
down_revision: str | None = 'f6b3d2e9a4c1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'wearable_connections',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('external_user_id', sa.Text(), nullable=True),
        sa.Column('credential', sa.Text(), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_wearable_connections_patient_id', 'wearable_connections',
                    ['patient_id'], unique=True)
    op.create_index('ix_wearable_connections_tenant_id', 'wearable_connections', ['tenant_id'])

    op.create_table(
        'wearable_daily',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('patient_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('sleep_minutes', sa.Integer(), nullable=True),
        sa.Column('resting_hr', sa.Integer(), nullable=True),
        sa.Column('hrv_ms', sa.Integer(), nullable=True),
        sa.Column('steps', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('patient_id', 'day', name='uq_wearable_daily_patient_day'),
    )
    op.create_index('ix_wearable_daily_patient_id', 'wearable_daily', ['patient_id'])
    op.create_index('ix_wearable_daily_tenant_id', 'wearable_daily', ['tenant_id'])
    op.create_index('ix_wearable_daily_day', 'wearable_daily', ['day'])


def downgrade() -> None:
    op.drop_table('wearable_daily')
    op.drop_table('wearable_connections')
