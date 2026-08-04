"""encrypt sensitive columns (name, contact to text)

Revision ID: 51cfc207ae18
Revises: 923357063c46
Create Date: 2026-08-04 00:30:23.397063
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '51cfc207ae18'
down_revision: str | None = '923357063c46'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # EncryptedText é armazenado como TEXT; o ciphertext (base64) não cabe em
    # VARCHAR(255). Alargamos as colunas de identificação do paciente para TEXT.
    op.alter_column('patients', 'name',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=False)
    op.alter_column('patients', 'contact',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=True)


def downgrade() -> None:
    op.alter_column('patients', 'contact',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=True)
    op.alter_column('patients', 'name',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
