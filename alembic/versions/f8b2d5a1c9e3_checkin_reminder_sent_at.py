"""dedupe do lembrete diário de check-in

Revision ID: f8b2d5a1c9e3
Revises: e7a1c4f9b2d5
Create Date: 2026-09-13 19:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f8b2d5a1c9e3'
down_revision: str | None = 'e7a1c4f9b2d5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'patients',
        sa.Column('checkin_reminder_sent_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('patients', 'checkin_reminder_sent_at')
