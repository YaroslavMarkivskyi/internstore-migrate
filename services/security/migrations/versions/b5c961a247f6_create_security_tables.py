"""create security tables

Revision ID: b5c961a247f6
Revises:
Create Date: 2026-08-01 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5c961a247f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Created automatically as part of op.create_table('users', ...) below
    # (SQLAlchemy's Enum type creates/drops itself alongside the table it's
    # first used in) — reused as-is (not re-declared) for visit_log.auth_type
    # below so CREATE TYPE only runs once.
    auth_type = sa.Enum('fingerprint', 'nfc', name='auth_type')

    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('auth_type', auth_type, nullable=False),
        sa.Column('credential', sa.String(), nullable=False),
        sa.Column('warehouse_ids', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'warehouses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'access_rules',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('warehouse_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'warehouse_id'),
    )

    op.create_table(
        'visit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('warehouse_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('auth_type', auth_type, nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('video_url', sa.String(), nullable=True),
        sa.Column('denial_reason', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['warehouse_id'], ['warehouses.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_visit_log_warehouse_id', 'visit_log', ['warehouse_id'])
    op.create_index('ix_visit_log_user_id', 'visit_log', ['user_id'])
    op.create_index('ix_visit_log_attempted_at', 'visit_log', ['attempted_at'])


def downgrade() -> None:
    op.drop_index('ix_visit_log_attempted_at', table_name='visit_log')
    op.drop_index('ix_visit_log_user_id', table_name='visit_log')
    op.drop_index('ix_visit_log_warehouse_id', table_name='visit_log')
    op.drop_table('visit_log')
    op.drop_table('access_rules')
    op.drop_table('warehouses')
    op.drop_table('users')
    # auth_type is dropped automatically by op.drop_table('users') above.
