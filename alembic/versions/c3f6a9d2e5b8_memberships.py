"""memberships (usuário × tenant × papel) + backfill owner por médico

Revision ID: c3f6a9d2e5b8
Revises: b2e5c8f1a4d7
Create Date: 2026-09-19 10:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3f6a9d2e5b8'
down_revision: str | None = 'b2e5c8f1a4d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE = sa.Enum('OWNER', 'DOCTOR', 'RECEPTION', 'FINANCE', name='clinic_role')


def upgrade() -> None:
    op.create_table(
        'memberships',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', _ROLE, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'tenant_id', name='uq_membership_user_tenant'),
    )
    op.create_index('ix_memberships_user_id', 'memberships', ['user_id'])
    op.create_index('ix_memberships_tenant_id', 'memberships', ['tenant_id'])

    # Backfill: cada médico atual vira OWNER do seu tenant (conta solo = 1 pessoa).
    op.execute(
        """
        INSERT INTO memberships (id, user_id, tenant_id, role, is_active, created_at, updated_at)
        SELECT gen_random_uuid(), d.user_id, d.tenant_id, 'OWNER'::clinic_role, true, now(), now()
        FROM doctors d
        ON CONFLICT (user_id, tenant_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index('ix_memberships_tenant_id', table_name='memberships')
    op.drop_index('ix_memberships_user_id', table_name='memberships')
    op.drop_table('memberships')
    _ROLE.drop(op.get_bind(), checkfirst=True)
