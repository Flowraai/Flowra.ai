"""encrypt exam/prescription clinical fields at rest

LGPD — cifra o conteúdo clínico de exames e receitas (nome/observações do exame,
itens/observações da receita). Colunas viram TEXT (EncryptedText/EncryptedJSON):
o ORM cifra na gravação e decifra na leitura; linhas existentes ficam legíveis
(adoção gradual). As colunas `notes` já eram TEXT — sem ALTER, só passam a cifrar.

Revision ID: f2c8d3a45b61
Revises: e7a3f1b9c0d4
Create Date: 2026-08-10 00:20:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f2c8d3a45b61'
down_revision: str | None = 'e7a3f1b9c0d4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # EncryptedText grava base64 do ciphertext — não cabe em VARCHAR(255).
    op.alter_column(
        'exams', 'name',
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )
    # items: JSONB -> TEXT (EncryptedJSON). `::text` preserva o JSON existente.
    op.alter_column(
        'prescriptions', 'items',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        type_=sa.Text(),
        existing_nullable=False,
        postgresql_using='items::text',
    )


def downgrade() -> None:
    # ATENÇÃO: `::jsonb` só funciona se os dados estiverem em claro (sem cifra).
    op.alter_column(
        'prescriptions', 'items',
        existing_type=sa.Text(),
        type_=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=False,
        postgresql_using='items::jsonb',
    )
    op.alter_column(
        'exams', 'name',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
