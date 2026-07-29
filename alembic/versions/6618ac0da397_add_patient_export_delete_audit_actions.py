"""add patient export/delete audit actions

Revision ID: 6618ac0da397
Revises: eacacd5c7526
Create Date: 2026-07-29 12:01:54.023329
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '6618ac0da397'
down_revision: str | None = 'eacacd5c7526'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'patient_exported'")
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'patient_deleted'")


def downgrade() -> None:
    # PostgreSQL não remove valores de enum de forma trivial; no-op.
    pass
