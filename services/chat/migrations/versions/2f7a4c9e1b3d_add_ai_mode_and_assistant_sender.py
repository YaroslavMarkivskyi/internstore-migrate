"""add ai_mode column and assistant sender_type

Revision ID: 2f7a4c9e1b3d
Revises: 1a2b3c4d5e6f
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f7a4c9e1b3d'
down_revision: Union[str, None] = '1a2b3c4d5e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('rooms', sa.Column('ai_mode', sa.Boolean(), nullable=False, server_default='true'))
    # ADD VALUE can't be used in the same transaction as reading the new
    # value back out, but this migration only adds it — nothing here (or in
    # this same transaction) inserts an 'assistant' row.
    op.execute("ALTER TYPE sender_type ADD VALUE IF NOT EXISTS 'assistant'")


def downgrade() -> None:
    op.drop_column('rooms', 'ai_mode')
    # Postgres has no ALTER TYPE ... DROP VALUE — removing 'assistant' would
    # require rebuilding the enum type, which isn't worth it for a downgrade
    # path; any 'assistant' rows already written would block it anyway.
