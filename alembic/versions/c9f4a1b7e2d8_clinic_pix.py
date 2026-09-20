"""cobrança centralizada na clínica: PIX do tenant

Revision ID: c9f4a1b7e2d8
Revises: b8e3c6f1d4a9
Create Date: 2026-09-20 20:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c9f4a1b7e2d8'
down_revision: str | None = 'b8e3c6f1d4a9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Recebimento centralizado: quando ligado, o PIX das cobranças usa a chave da
    # clínica (não a do médico). Padrão desligado preserva o comportamento solo.
    op.add_column(
        'tenants',
        sa.Column('pix_centralized', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # EncryptedText é armazenado como TEXT (base64 do ciphertext).
    op.add_column('tenants', sa.Column('pix_key', sa.Text(), nullable=True))
    op.add_column('tenants', sa.Column('pix_city', sa.String(length=60), nullable=True))
    op.add_column('tenants', sa.Column('pix_receiver_name', sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'pix_receiver_name')
    op.drop_column('tenants', 'pix_city')
    op.drop_column('tenants', 'pix_key')
    op.drop_column('tenants', 'pix_centralized')
