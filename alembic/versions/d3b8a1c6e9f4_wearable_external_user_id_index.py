"""índice de wearable_connections.external_user_id (lookup no webhook Terra)

Revision ID: d3b8a1c6e9f4
Revises: c1d9f4a7e6b2
Create Date: 2026-09-10 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'd3b8a1c6e9f4'
down_revision: str | None = 'c1d9f4a7e6b2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        'ix_wearable_connections_external_user_id',
        'wearable_connections', ['external_user_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_wearable_connections_external_user_id', table_name='wearable_connections')
