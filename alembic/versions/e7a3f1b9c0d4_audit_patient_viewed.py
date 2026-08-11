"""add PATIENT_VIEWED audit action (LGPD-5 — auditar leitura de dado clínico)

Revision ID: e7a3f1b9c0d4
Revises: d4b2c1a09e77
Create Date: 2026-08-10 00:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = 'e7a3f1b9c0d4'
down_revision: str | None = 'd4b2c1a09e77'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # O SQLAlchemy grava enums pelo NOME do membro (maiúsculo).
    op.execute("ALTER TYPE audit_action ADD VALUE IF NOT EXISTS 'PATIENT_VIEWED'")


def downgrade() -> None:
    # PostgreSQL não remove valores de enum de forma trivial; no-op.
    pass
