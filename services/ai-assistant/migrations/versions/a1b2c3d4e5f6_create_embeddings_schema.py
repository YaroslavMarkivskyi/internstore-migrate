"""create product_embeddings and processed_events

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'product_embeddings',
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=250), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('embedding', Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('product_id'),
    )

    op.create_table(
        'processed_events',
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('event_id'),
    )


def downgrade() -> None:
    op.drop_table('processed_events')
    op.drop_table('product_embeddings')
