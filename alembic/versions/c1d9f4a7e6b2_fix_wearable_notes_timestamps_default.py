"""corrige DEFAULT de created_at/updated_at (wearable + anotações)

As migrações que criaram wearable_connections, wearable_daily e clinical_notes
declararam created_at/updated_at como NOT NULL sem DEFAULT. Como o INSERT do ORM
não envia essas colunas (o modelo usa server_default), o banco migrado rejeitava
o insert (NOT NULL). Aqui aplicamos SET DEFAULT now() nessas colunas.

Revision ID: c1d9f4a7e6b2
Revises: b8e5c2a1f7d3
Create Date: 2026-09-09 21:15:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c1d9f4a7e6b2'
down_revision: str | None = 'b8e5c2a1f7d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("wearable_connections", "wearable_daily", "clinical_notes")


def upgrade() -> None:
    for table in _TABLES:
        for col in ("created_at", "updated_at"):
            op.alter_column(
                table, col,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=sa.text("now()"),
            )


def downgrade() -> None:
    for table in _TABLES:
        for col in ("created_at", "updated_at"):
            op.alter_column(
                table, col,
                existing_type=sa.DateTime(timezone=True),
                existing_nullable=False,
                server_default=None,
            )
