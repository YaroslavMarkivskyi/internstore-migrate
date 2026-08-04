"""add product is_deleted

Revision ID: a3f6c1d8e2b7
Revises: ce2905ae1974
Create Date: 2026-08-04 11:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f6c1d8e2b7'
down_revision: Union[str, None] = 'ce2905ae1974'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    )


def downgrade() -> None:
    op.drop_column('products', 'is_deleted')
