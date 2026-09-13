"""lançamentos financeiros por consulta (a receber / recebido)

Revision ID: d6f9a2c4e8b1
Revises: c5e8f1b3d7a9
Create Date: 2026-09-13 17:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = 'd6f9a2c4e8b1'
down_revision: str | None = 'c5e8f1b3d7a9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'consultation_charges',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('appointment_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('health_plan_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('health_plans.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kind', sa.String(length=12), nullable=False),
        sa.Column('gross_cents', sa.Integer(), server_default='0', nullable=False),
        sa.Column('doctor_cents', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=12), server_default='pending', nullable=False),
        sa.Column('payment_method', sa.String(length=12), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('appointment_id', name='uq_charge_appointment'),
    )
    op.create_index('ix_consultation_charges_tenant_id', 'consultation_charges', ['tenant_id'])
    op.create_index('ix_consultation_charges_patient_id', 'consultation_charges', ['patient_id'])
    op.create_index('ix_consultation_charges_doctor_id', 'consultation_charges', ['doctor_id'])


def downgrade() -> None:
    op.drop_table('consultation_charges')
