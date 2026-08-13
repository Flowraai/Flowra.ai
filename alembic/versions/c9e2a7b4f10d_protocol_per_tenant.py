"""protocol per tenant (pesquisa editável pelo médico)

Revision ID: c9e2a7b4f10d
Revises: b8d1f0a4c6e9
Create Date: 2026-08-12 13:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'c9e2a7b4f10d'
down_revision: str | None = 'b8d1f0a4c6e9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'protocols',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f('ix_protocols_tenant_id'), 'protocols', ['tenant_id'], unique=False)
    op.create_foreign_key(
        'fk_protocols_tenant_id', 'protocols', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE'
    )
    # Cópias por tenant repetem specialty/version do template global -> remove a
    # unicidade (specialty, version) que impediria as cópias.
    op.drop_constraint('uq_protocol_specialty_version', 'protocols', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint(
        'uq_protocol_specialty_version', 'protocols', ['specialty', 'version']
    )
    op.drop_constraint('fk_protocols_tenant_id', 'protocols', type_='foreignkey')
    op.drop_index(op.f('ix_protocols_tenant_id'), table_name='protocols')
    op.drop_column('protocols', 'tenant_id')
