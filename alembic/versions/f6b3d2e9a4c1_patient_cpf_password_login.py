"""login do paciente por CPF + senha (ativação, reset por código)

Revision ID: f6b3d2e9a4c1
Revises: e5f2a9c1b3d8
Create Date: 2026-09-09 19:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f6b3d2e9a4c1'
down_revision: str | None = 'e5f2a9c1b3d8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('patients', sa.Column('cpf_hash', sa.String(length=64), nullable=True))
    op.add_column('patients', sa.Column('password_hash', sa.String(length=255), nullable=True))
    op.add_column('patients', sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('patients', sa.Column('pwd_reset_code_hash', sa.String(length=64), nullable=True))
    op.add_column(
        'patients', sa.Column('pwd_reset_expires_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_patients_cpf_hash', 'patients', ['cpf_hash'])
    # Um CPF só pode ter uma conta (índice único parcial — ignora quem ainda não ativou).
    op.create_index(
        'uq_patients_cpf_hash', 'patients', ['cpf_hash'],
        unique=True, postgresql_where=sa.text('cpf_hash IS NOT NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_patients_cpf_hash', table_name='patients')
    op.drop_index('ix_patients_cpf_hash', table_name='patients')
    op.drop_column('patients', 'pwd_reset_expires_at')
    op.drop_column('patients', 'pwd_reset_code_hash')
    op.drop_column('patients', 'activated_at')
    op.drop_column('patients', 'password_hash')
    op.drop_column('patients', 'cpf_hash')
