"""permissão por usuário: recepção enxerga o financeiro

Revision ID: d4a7b1e6c9f2
Revises: c3f6a9d2e5b8
Create Date: 2026-09-19 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4a7b1e6c9f2'
down_revision: str | None = 'c3f6a9d2e5b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'memberships',
        sa.Column('can_view_finance', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('memberships', 'can_view_finance')
