"""stock_items.is_unavailable, telemetry-events consumer support

Revision ID: 6a2c1f4e9b03
Revises: 3f7b6a2e9c44
Create Date: 2026-08-01 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a2c1f4e9b03'
down_revision: Union[str, None] = '3f7b6a2e9c44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'stock_items',
        sa.Column('is_unavailable', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_column('stock_items', 'is_unavailable')
