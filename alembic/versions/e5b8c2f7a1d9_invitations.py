"""convites para entrar na clínica (tenant)

Revision ID: e5b8c2f7a1d9
Revises: d4a7b1e6c9f2
Create Date: 2026-09-19 14:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'e5b8c2f7a1d9'
down_revision: str | None = 'd4a7b1e6c9f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'invitations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        # Reaproveita o tipo clinic_role já existente (não recria).
        sa.Column('role', postgresql.ENUM(name='clinic_role', create_type=False), nullable=False),
        sa.Column('can_view_finance', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('invited_by_user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('token_hash', name='uq_invitation_token_hash'),
    )
    op.create_index('ix_invitations_tenant_id', 'invitations', ['tenant_id'])
    op.create_index('ix_invitations_email', 'invitations', ['email'])
    op.create_index('ix_invitations_token_hash', 'invitations', ['token_hash'])


def downgrade() -> None:
    op.drop_index('ix_invitations_token_hash', table_name='invitations')
    op.drop_index('ix_invitations_email', table_name='invitations')
    op.drop_index('ix_invitations_tenant_id', table_name='invitations')
    op.drop_table('invitations')
