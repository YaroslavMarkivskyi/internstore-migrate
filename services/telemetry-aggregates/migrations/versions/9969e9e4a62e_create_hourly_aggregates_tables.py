"""create hourly_aggregates tables

Revision ID: 9969e9e4a62e
Revises:
Create Date: 2026-08-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9969e9e4a62e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'hourly_aggregates',
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('hour_bucket', sa.DateTime(timezone=True), nullable=False),
        sa.Column('avg_temperature', sa.Numeric(), nullable=False),
        sa.Column('min_temperature', sa.Numeric(), nullable=False),
        sa.Column('max_temperature', sa.Numeric(), nullable=False),
        sa.Column('reading_count', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('store_id', 'product_id', 'hour_bucket'),
    )

    op.create_table(
        'processed_events',
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('event_id'),
    )


def downgrade() -> None:
    op.drop_table('processed_events')
    op.drop_table('hourly_aggregates')
