"""stocks.humidity

Revision ID: 9c3d5f7a1b02
Revises: 6a2c1f4e9b03
Create Date: 2026-08-03 20:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c3d5f7a1b02'
down_revision: Union[str, None] = '6a2c1f4e9b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('stocks', sa.Column('humidity', sa.Numeric(), nullable=True))


def downgrade() -> None:
    op.drop_column('stocks', 'humidity')
