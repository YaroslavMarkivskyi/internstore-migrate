"""create help_chunks

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-31 09:40:00.000000

Customer-facing FAQ / policy chunks for the shopping agent's non-product
retrieval (delivery, returns, payment, cold chain). Populated by
`ai_assistant.seed_help` from `help/*.md`, read (via AI_DB_URL) by
mcp-gateway's `search_help` tool — same store-in-ai-db / mirror-in-gateway
pattern as product_embeddings.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        'help_chunks',
        # Deterministic id = uuid5(source + heading + ordinal) so re-seeding
        # upserts in place rather than churning rows / leaving orphans.
        sa.Column('chunk_id', sa.Uuid(), nullable=False),
        sa.Column('source', sa.String(length=200), nullable=False),
        sa.Column('heading', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(EMBEDDING_DIMENSIONS), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('chunk_id'),
    )


def downgrade() -> None:
    op.drop_table('help_chunks')
