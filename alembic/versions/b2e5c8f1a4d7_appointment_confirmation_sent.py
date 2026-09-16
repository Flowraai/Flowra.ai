"""confirmação de consulta enviada (data/hora do envio)

Revision ID: b2e5c8f1a4d7
Revises: a1d4f7c2e9b6
Create Date: 2026-09-16 09:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b2e5c8f1a4d7'
down_revision: str | None = 'a1d4f7c2e9b6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'appointments',
        sa.Column('confirmation_sent_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('appointments', 'confirmation_sent_at')
