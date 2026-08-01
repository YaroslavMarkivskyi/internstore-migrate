"""create carts and orders

Revision ID: fd263b14ded7
Revises:
Create Date: 2026-08-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd263b14ded7'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Created automatically as part of op.create_table('orders', ...) below
    # (SQLAlchemy's Enum type creates/drops itself alongside the table it's
    # first used in) — no separate CREATE TYPE step needed.
    order_status = sa.Enum('new', name='order_status')

    op.create_table(
        'carts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id'),
    )
    op.create_index(op.f('ix_carts_owner_id'), 'carts', ['owner_id'], unique=True)

    op.create_table(
        'cart_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('cart_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['cart_id'], ['carts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cart_id', 'product_id', name='uq_cart_item_product'),
    )

    op.create_table(
        'orders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('owner_id', sa.String(length=255), nullable=False),
        sa.Column('status', order_status, nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=False),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_orders_owner_id'), 'orders', ['owner_id'], unique=False)

    op.create_table(
        'order_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('order_id', sa.Uuid(), nullable=False),
        sa.Column('product_id', sa.Uuid(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('order_items')
    op.drop_index(op.f('ix_orders_owner_id'), table_name='orders')
    op.drop_table('orders')
    op.drop_table('cart_items')
    op.drop_index(op.f('ix_carts_owner_id'), table_name='carts')
    op.drop_table('carts')
    # order_status is dropped automatically by op.drop_table('orders') above.
