"""create agent_memories

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-01 10:30:00.000000

Durable per-customer facts distilled from past shopping conversations,
embedded for retrieval by ADK's memory service (see adk/memory.py). Same
store-in-ai-db / pgvector pattern as product_embeddings and help_chunks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'agent_memories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('app_name', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.String(length=128), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_agent_memories_user_id', 'agent_memories', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_agent_memories_user_id', table_name='agent_memories')
    op.drop_table('agent_memories')
