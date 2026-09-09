"""doctor whatsapp instance (Evolution API por médico)

Revision ID: d4a1b8c7e2f3
Revises: c9e2a7b4f10d
Create Date: 2026-09-09 14:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4a1b8c7e2f3'
down_revision: str | None = 'c9e2a7b4f10d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('doctors', sa.Column('whatsapp_instance', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('doctors', 'whatsapp_instance')
