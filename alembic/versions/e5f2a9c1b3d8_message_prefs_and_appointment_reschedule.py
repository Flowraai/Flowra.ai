"""message prefs (por médico) + pedido de remarcação de consulta

Revision ID: e5f2a9c1b3d8
Revises: d4a1b8c7e2f3
Create Date: 2026-09-09 16:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f2a9c1b3d8'
down_revision: str | None = 'd4a1b8c7e2f3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # O que o médico envia por mensagem ao paciente (config, não é dado clínico).
    op.add_column('doctors', sa.Column('message_prefs', sa.JSON(), nullable=True))
    # Pedido de remarcação feito pelo paciente pelo app.
    op.add_column(
        'appointments',
        sa.Column('reschedule_requested_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column('appointments', sa.Column('reschedule_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('appointments', 'reschedule_note')
    op.drop_column('appointments', 'reschedule_requested_at')
    op.drop_column('doctors', 'message_prefs')
