"""nome de exibição do integrante (membership.name) + backfill

Revision ID: f6c9d3a8e2b1
Revises: e5b8c2f7a1d9
Create Date: 2026-09-20 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f6c9d3a8e2b1'
down_revision: str | None = 'e5b8c2f7a1d9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('memberships', sa.Column('name', sa.String(length=255), nullable=True))
    # Backfill: espelha o nome do Doctor (mesmo user+tenant) nos memberships atuais.
    op.execute(
        """
        UPDATE memberships m
        SET name = d.name
        FROM doctors d
        WHERE d.user_id = m.user_id AND d.tenant_id = m.tenant_id AND m.name IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column('memberships', 'name')
