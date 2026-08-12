"""doctor prescription provider + credential

Revision ID: b8d1f0a4c6e9
Revises: a3f9c1e2d5b7
Create Date: 2026-08-12 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b8d1f0a4c6e9'
down_revision: str | None = 'a3f9c1e2d5b7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('doctors', sa.Column('prescription_provider', sa.String(length=40), nullable=True))
    # Credencial do médico (token) cifrada em repouso -> Text.
    op.add_column('doctors', sa.Column('prescription_credential', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('doctors', 'prescription_credential')
    op.drop_column('doctors', 'prescription_provider')
