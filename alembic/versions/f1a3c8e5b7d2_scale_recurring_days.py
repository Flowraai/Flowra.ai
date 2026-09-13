"""escalas recorrentes (recurring_days)

Revision ID: f1a3c8e5b7d2
Revises: e9f1a2c7d4b6
Create Date: 2026-09-13 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f1a3c8e5b7d2'
down_revision: str | None = 'e9f1a2c7d4b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('scale_entries', sa.Column('recurring_days', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('scale_entries', 'recurring_days')
