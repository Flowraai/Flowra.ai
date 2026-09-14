"""chave PIX do médico (cobrança particular copia e cola)

Revision ID: a1d4f7c2e9b6
Revises: f8b2d5a1c9e3
Create Date: 2026-09-14 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a1d4f7c2e9b6'
down_revision: str | None = 'f8b2d5a1c9e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('doctors', sa.Column('pix_key', sa.Text(), nullable=True))
    op.add_column('doctors', sa.Column('pix_city', sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column('doctors', 'pix_city')
    op.drop_column('doctors', 'pix_key')
