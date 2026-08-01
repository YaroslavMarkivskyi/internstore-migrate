"""reservation saga: reserved_quantity, reservations, processed/outbox events

Revision ID: 3f7b6a2e9c44
Revises: 21130f828cfd
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f7b6a2e9c44'
down_revision: Union[str, None] = '21130f828cfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'stock_items',
        sa.Column('reserved_quantity', sa.Integer(), nullable=False, server_default='0'),
    )

    reservation_status = sa.Enum('reserved', 'consumed', 'released', name='reservation_status')

    op.create_table(
        'reservations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('order_id', sa.Uuid(), nullable=False),
        sa.Column('status', reservation_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id'),
    )
    op.create_index(op.f('ix_reservations_order_id'), 'reservations', ['order_id'], unique=True)

    op.create_table(
        'reservation_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('reservation_id', sa.Uuid(), nullable=False),
        sa.Column('stock_item_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ),
        sa.ForeignKeyConstraint(['stock_item_id'], ['stock_items.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'processed_events',
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('event_id'),
    )

    op.create_table(
        'outbox_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_outbox_events_unpublished',
        'outbox_events',
        ['created_at'],
        postgresql_where=sa.text('published_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_outbox_events_unpublished', table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_table('processed_events')
    op.drop_table('reservation_items')
    op.drop_index(op.f('ix_reservations_order_id'), table_name='reservations')
    op.drop_table('reservations')
    op.execute('DROP TYPE reservation_status')
    op.drop_column('stock_items', 'reserved_quantity')
