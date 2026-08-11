"""STR-149: event sourcing schema -- stock_events (append-only source of
truth for the (stock_id, product_id) aggregate) and stock_snapshots
(periodic, replay-cost-bounding only -- see README.md's "Event sourcing"
section for the full design). Also adds the stock_items(stock_id,
product_id) unique constraint: not load-bearing (the projector is the
sole writer, already serialized by stock_events' own UNIQUE(aggregate_id,
sequence_number)), but cheap defense-in-depth once "one row per pair" is
an invariant this design actually depends on.

Pure DDL, additive -- safe to deploy standalone, ahead of both the data
backfill migration and the code cutover (see the follow-up
backfill_stock_events migration and README.md's rollout section).

Revision ID: 99d45f76e7ae
Revises: 9c3d5f7a1b02
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99d45f76e7ae'
down_revision: Union[str, None] = '9c3d5f7a1b02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('aggregate_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('sequence_number', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aggregate_id', 'sequence_number', name='uq_stock_events_aggregate_sequence'),
    )
    op.create_index(op.f('ix_stock_events_aggregate_id'), 'stock_events', ['aggregate_id'])

    op.create_table(
        'stock_snapshots',
        sa.Column('aggregate_id', sa.Uuid(), nullable=False),
        sa.Column('sequence_number', sa.BigInteger(), nullable=False),
        sa.Column('state', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('aggregate_id', 'sequence_number'),
    )

    # NOTE: the pre-STR-149 receive/move handlers used a select-then-upsert
    # pattern with no DB-level uniqueness guard (see the pre-STR-149
    # StockItem docstring) -- if two rows for the same (stock_id,
    # product_id) somehow exist in production data, this constraint will
    # fail to create and must be resolved (merge the duplicate rows) before
    # this migration can proceed. That failure is the desired behavior:
    # surfacing a pre-existing data-quality issue loudly here beats the
    # event-sourced design silently picking one of two rows as "the"
    # projection for that aggregate going forward.
    op.create_unique_constraint('uq_stock_items_stock_product', 'stock_items', ['stock_id', 'product_id'])


def downgrade() -> None:
    op.drop_constraint('uq_stock_items_stock_product', 'stock_items', type_='unique')
    op.drop_table('stock_snapshots')
    op.drop_index(op.f('ix_stock_events_aggregate_id'), table_name='stock_events')
    op.drop_table('stock_events')
