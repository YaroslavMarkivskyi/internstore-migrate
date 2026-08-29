"""rename messages.attachment_url to attachment_key

Revision ID: a7c8d9e0f1a2
Revises: 2f7a4c9e1b3d
Create Date: 2026-08-21 00:00:00.000000

The bucket chat attachments live in is private (see terraform/gcp/modules/
storage's comment and ObjectStorageClient's docstring) -- there's no public
URL to store anymore. The column now holds the object-storage object key;
every outbound message representation signs a fresh presigned
attachment_url from it at serve time (see routers/rooms.py's get_messages
and ws/room.py's _send_history/live publish), never persisting one.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c8d9e0f1a2'
down_revision: Union[str, None] = '2f7a4c9e1b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('messages', 'attachment_url', new_column_name='attachment_key')


def downgrade() -> None:
    op.alter_column('messages', 'attachment_key', new_column_name='attachment_url')
