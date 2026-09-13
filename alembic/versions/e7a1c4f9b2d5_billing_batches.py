"""lotes de faturamento de convênio + vínculo na cobrança

Revision ID: e7a1c4f9b2d5
Revises: d6f9a2c4e8b1
Create Date: 2026-09-13 18:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = 'e7a1c4f9b2d5'
down_revision: str | None = 'd6f9a2c4e8b1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'billing_batches',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('health_plan_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('health_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reference', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=12), server_default='open', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_billing_batches_tenant_id', 'billing_batches', ['tenant_id'])
    op.create_index('ix_billing_batches_doctor_id', 'billing_batches', ['doctor_id'])

    op.add_column(
        'consultation_charges',
        sa.Column('batch_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('billing_batches.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_consultation_charges_batch_id', 'consultation_charges', ['batch_id'])


def downgrade() -> None:
    op.drop_index('ix_consultation_charges_batch_id', table_name='consultation_charges')
    op.drop_column('consultation_charges', 'batch_id')
    op.drop_table('billing_batches')
