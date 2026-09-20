"""rateio clínica×médico: doctors.clinic_share_percent + charges.clinic_cents

Revision ID: b8e3c6f1d4a9
Revises: a7d2f9c4b8e6
Create Date: 2026-09-20 18:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8e3c6f1d4a9'
down_revision: str | None = 'a7d2f9c4b8e6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'doctors',
        sa.Column('clinic_share_percent', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'consultation_charges',
        sa.Column('clinic_cents', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('consultation_charges', 'clinic_cents')
    op.drop_column('doctors', 'clinic_share_percent')
