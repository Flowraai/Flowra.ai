"""plans and subscriptions (billing)

Revision ID: a1c7e9b4d2f0
Revises: 51cfc207ae18
Create Date: 2026-08-04 20:10:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = 'a1c7e9b4d2f0'
down_revision: str | None = '51cfc207ae18'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_cents', sa.Integer(), nullable=False),
        sa.Column('cycle', sa.String(length=20), server_default='monthly', nullable=False),
        sa.Column('patient_limit', sa.Integer(), nullable=True),
        sa.Column('trial_days', sa.Integer(), server_default='0', nullable=False),
        sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # Cria o tipo enum explicitamente (create_table não o cria sozinho no Postgres).
    subscription_status = postgresql.ENUM(
        'TRIALING', 'PENDING', 'ACTIVE', 'OVERDUE', 'CANCELED',
        name='subscription_status',
        create_type=False,
    )
    subscription_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', subscription_status, server_default='PENDING', nullable=False),
        sa.Column('gateway_customer_id', sa.String(length=64), nullable=True),
        sa.Column('gateway_subscription_id', sa.String(length=64), nullable=True),
        sa.Column('card_last4', sa.String(length=4), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_subscriptions_tenant_id'), 'subscriptions', ['tenant_id'], unique=True
    )
    op.create_index(
        op.f('ix_subscriptions_gateway_subscription_id'),
        'subscriptions',
        ['gateway_subscription_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_subscriptions_gateway_subscription_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_tenant_id'), table_name='subscriptions')
    op.drop_table('subscriptions')
    sa.Enum(name='subscription_status').drop(op.get_bind(), checkfirst=True)
    op.drop_table('plans')
