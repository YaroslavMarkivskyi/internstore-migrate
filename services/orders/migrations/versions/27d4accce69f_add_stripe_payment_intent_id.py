"""add stripe_payment_intent_id to orders

Revision ID: 27d4accce69f
Revises: 8a1f2c9d4e10
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27d4accce69f'
down_revision: Union[str, None] = '8a1f2c9d4e10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        'uq_orders_stripe_payment_intent_id', 'orders', ['stripe_payment_intent_id']
    )


def downgrade() -> None:
    op.drop_constraint('uq_orders_stripe_payment_intent_id', 'orders', type_='unique')
    op.drop_column('orders', 'stripe_payment_intent_id')
