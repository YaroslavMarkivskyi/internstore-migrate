"""reservation saga: extend order_status, add outbox_events

Revision ID: 8a1f2c9d4e10
Revises: fd263b14ded7
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a1f2c9d4e10'
down_revision: Union[str, None] = 'fd263b14ded7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive: new enum labels only, no restructuring of the column or
    # existing rows. ALTER TYPE ... ADD VALUE cannot run inside the same
    # transaction as a statement that *uses* the new value, but is fine as
    # standalone DDL on Postgres 12+ (this stack runs 16) — each ADD VALUE
    # here is its own statement and nothing in this migration reads the new
    # values back.
    for value in ("pending", "paid", "done", "cancelled", "rejected"):
        op.execute(f"ALTER TYPE order_status ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table(
        'outbox_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    # Partial index — the poller only ever scans unpublished rows.
    op.create_index(
        'ix_outbox_events_unpublished',
        'outbox_events',
        ['created_at'],
        postgresql_where=sa.text('published_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_outbox_events_unpublished', table_name='outbox_events')
    op.drop_table('outbox_events')
    # Postgres has no ALTER TYPE ... DROP VALUE — removing the added enum
    # labels would require rebuilding the type entirely. Not reversible.
