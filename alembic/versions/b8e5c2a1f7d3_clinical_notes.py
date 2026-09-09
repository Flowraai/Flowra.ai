"""anotações clínicas (prontuário) — evolução, diagnóstico, outros

Revision ID: b8e5c2a1f7d3
Revises: a7c4e1f9b2d6
Create Date: 2026-09-09 20:45:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = 'b8e5c2a1f7d3'
down_revision: str | None = 'a7c4e1f9b2d6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'clinical_notes',
        sa.Column('id', PgUUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('doctors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('appointment_id', PgUUID(as_uuid=True),
                  sa.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('kind', sa.String(length=20), nullable=False, server_default='note'),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_clinical_notes_tenant_id', 'clinical_notes', ['tenant_id'])
    op.create_index('ix_clinical_notes_patient_id', 'clinical_notes', ['patient_id'])
    op.create_index('ix_clinical_notes_appointment_id', 'clinical_notes', ['appointment_id'])


def downgrade() -> None:
    op.drop_table('clinical_notes')
