"""encrypt checkin clinical fields (structured_responses, risk_reasons, category_risks)

LGPD-1 — os campos clínicos estruturados do check-in eram gravados em claro
(JSONB), mesmo com a cifragem em repouso ligada: humor, ansiedade, flag de
crise/ideação, motivos do risco e risco por categoria. Aqui convertemos as três
colunas para TEXT (EncryptedJSON): o ORM passa a cifrar na gravação e decifrar na
leitura. As linhas existentes viram JSON em claro (`::text`) e continuam legíveis
(adoção gradual); as novas gravações já saem cifradas.

Revision ID: d4b2c1a09e77
Revises: a1c7e9b4d2f0
Create Date: 2026-08-10 00:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd4b2c1a09e77'
down_revision: str | None = 'a1c7e9b4d2f0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_COLUMNS = ('structured_responses', 'risk_reasons', 'category_risks')


def upgrade() -> None:
    # JSONB -> TEXT. O `::text` preserva o JSON existente (fica em claro, legível
    # pelo EncryptedJSON como legado); novas gravações são cifradas pelo ORM.
    for col in _COLUMNS:
        op.alter_column(
            'checkins', col,
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
            type_=sa.Text(),
            existing_nullable=False,
            postgresql_using=f'{col}::text',
        )


def downgrade() -> None:
    # TEXT -> JSONB. ATENÇÃO: só funciona se os valores estiverem em claro (JSON).
    # Se já houver dados cifrados (prefixo enc:v1:), o cast `::jsonb` falha — a
    # cifragem em repouso é, por natureza, um caminho sem volta automático.
    for col in _COLUMNS:
        op.alter_column(
            'checkins', col,
            existing_type=sa.Text(),
            type_=postgresql.JSONB(astext_type=sa.Text()),
            existing_nullable=False,
            postgresql_using=f'{col}::jsonb',
        )
