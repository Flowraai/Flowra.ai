"""patient_updated audit action

Revision ID: 3f57b72eb4f2
Revises: 03f10a3c261f
Create Date: 2026-07-30 00:50:13.901836
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '3f57b72eb4f2'
down_revision: str | None = '03f10a3c261f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nome MAIÚSCULO, como o ORM grava enums.
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'PATIENT_UPDATED'")


def downgrade() -> None:
    # PostgreSQL não remove valores de enum de forma trivial; no-op.
    pass
