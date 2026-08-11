"""add patients.ai_consent_at (LGPD-4 — consentimento p/ IA externa)

Revision ID: a3f9c1e2d5b7
Revises: f2c8d3a45b61
Create Date: 2026-08-10 00:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'a3f9c1e2d5b7'
down_revision: str | None = 'f2c8d3a45b61'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'patients',
        sa.Column('ai_consent_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('patients', 'ai_consent_at')
