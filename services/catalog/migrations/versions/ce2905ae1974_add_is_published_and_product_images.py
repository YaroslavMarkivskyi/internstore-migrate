"""add is_published and product_images

Revision ID: ce2905ae1974
Revises: 8f1b9513174b
Create Date: 2026-08-03 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ce2905ae1974'
down_revision: Union[str, None] = '8f1b9513174b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('is_published', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )

    op.create_table(
        'product_images',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('image', sa.String(), nullable=False),
        sa.Column('object_key', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('product_images')
    op.drop_column('products', 'is_published')
