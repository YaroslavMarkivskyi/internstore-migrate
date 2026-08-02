"""create chat schema

Revision ID: 1a2b3c4d5e6f
Revises:
Create Date: 2026-08-02 00:00:00.000000

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
    sender_type = sa.Enum('customer', 'admin', name='sender_type')

    op.create_table(
        'rooms',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('customer_id', sa.Uuid(), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notification_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'messages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('room_id', sa.String(length=255), nullable=False),
        sa.Column('sender_type', sender_type, nullable=False),
        sa.Column('sender_id', sa.String(length=255), nullable=False),
        sa.Column('content', sa.String(), nullable=True),
        sa.Column('attachment_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_messages_room_id'), 'messages', ['room_id'], unique=False)

    op.create_table(
        'room_members',
        sa.Column('room_id', sa.String(length=255), nullable=False),
        sa.Column('admin_id', sa.String(length=255), nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ),
        sa.PrimaryKeyConstraint('room_id', 'admin_id'),
    )

    op.create_table(
        'outbox_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_outbox_events_unpublished',
        'outbox_events',
        ['created_at'],
        postgresql_where=sa.text('published_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_outbox_events_unpublished', table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_table('room_members')
    op.drop_index(op.f('ix_messages_room_id'), table_name='messages')
    op.drop_table('messages')
    op.drop_table('rooms')
    # sender_type is dropped automatically by op.drop_table('messages') above.
