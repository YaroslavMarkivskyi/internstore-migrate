"""drop product_images.image public URL column

Revision ID: f1a2b3c4d5e6
Revises: a3f6c1d8e2b7
Create Date: 2026-08-21 00:00:00.000000

The bucket product images live in is private (see terraform/gcp/modules/
storage's comment and ObjectStorageClient's docstring) -- there's no public
URL to store anymore. `object_key` is the sole durable reference; every
response that needs an `image` URL signs one from it on the spot (see
routers/product_images.py), short-lived and never persisted, so a stored
public link never has the chance to go stale/403.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'a3f6c1d8e2b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('product_images', 'image')


def downgrade() -> None:
    # Downgrade path has no real URL to backfill with -- existing rows get
    # an empty string, same as any other lossy-downgrade column drop in
    # this migration set.
    op.add_column(
        'product_images',
        sa.Column('image', sa.String(), nullable=False, server_default=''),
    )
