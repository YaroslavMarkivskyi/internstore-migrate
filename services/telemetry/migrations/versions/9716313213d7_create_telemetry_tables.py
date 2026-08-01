"""create telemetry tables

Revision ID: 9716313213d7
Revises:
Create Date: 2026-08-01 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9716313213d7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stores',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('threshold_temp', sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'temperature_readings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('temperature', sa.Numeric(), nullable=False),
        sa.Column('humidity', sa.Numeric(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_temperature_readings_store_id', 'temperature_readings', ['store_id'])
    op.create_index('ix_temperature_readings_recorded_at', 'temperature_readings', ['recorded_at'])

    op.create_table(
        'incidents',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('temperature_at_outbreak', sa.Numeric(), nullable=False),
        sa.Column('deviation', sa.Numeric(), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_incidents_store_id', 'incidents', ['store_id'])

    op.create_table(
        'store_product_thresholds',
        sa.Column('store_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('max_temp', sa.Numeric(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ),
        sa.PrimaryKeyConstraint('store_id', 'product_id'),
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
    op.drop_table('store_product_thresholds')
    op.drop_index('ix_incidents_store_id', table_name='incidents')
    op.drop_table('incidents')
    op.drop_index('ix_temperature_readings_recorded_at', table_name='temperature_readings')
    op.drop_index('ix_temperature_readings_store_id', table_name='temperature_readings')
    op.drop_table('temperature_readings')
    op.drop_table('stores')
