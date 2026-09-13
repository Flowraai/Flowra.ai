"""convênios (planos de saúde do paciente) + vínculo no paciente

Revision ID: c5e8f1b3d7a9
Revises: b4d7e2a9c1f5
Create Date: 2026-09-13 16:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = 'c5e8f1b3d7a9'
down_revision: str | None = 'b4d7e2a9c1f5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'health_plans',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('ans_code', sa.String(length=20), nullable=True),
        sa.Column('payout_type', sa.String(length=12), server_default='fixed', nullable=False),
        sa.Column('payout_value_cents', sa.Integer(), nullable=True),
        sa.Column('payout_percent', sa.Integer(), nullable=True),
        sa.Column('default_consultation_cents', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_health_plans_tenant_id', 'health_plans', ['tenant_id'])
    op.create_index('ix_health_plans_doctor_id', 'health_plans', ['doctor_id'])

    op.add_column(
        'patients',
        sa.Column('health_plan_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('health_plans.id', ondelete='SET NULL'), nullable=True),
    )
    op.add_column('patients', sa.Column('insurance_card', sa.Text(), nullable=True))
    op.add_column('patients', sa.Column('insurance_valid_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('patients', 'insurance_valid_until')
    op.drop_column('patients', 'insurance_card')
    op.drop_column('patients', 'health_plan_id')
    op.drop_table('health_plans')
