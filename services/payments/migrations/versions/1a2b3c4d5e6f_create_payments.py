"""create payments

Revision ID: 1a2b3c4d5e6f
Revises:
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a2b3c4d5e6f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    payment_status = sa.Enum('charged', 'refunded', 'failed', name='payment_status')

    op.create_table(
        'payments',
        sa.Column('id', sa.Uuid(), nullable=False),
        # One Payment per Order — the idempotency key for POST /charge: a
        # retried/duplicate charge for the same order_id returns this row
        # instead of charging again. See payments/routers/payments.py.
        sa.Column('order_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('status', payment_status, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id'),
    )
    op.create_index(op.f('ix_payments_order_id'), 'payments', ['order_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_payments_order_id'), table_name='payments')
    op.drop_table('payments')
    payment_status = sa.Enum('charged', 'refunded', 'failed', name='payment_status')
    payment_status.drop(op.get_bind(), checkfirst=True)
