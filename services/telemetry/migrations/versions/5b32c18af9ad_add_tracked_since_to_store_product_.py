"""add tracked_since to store_product_thresholds (STR-148)

Revision ID: 5b32c18af9ad
Revises: 69ff8539f688
Create Date: 2026-08-11 00:10:00.000000

Found during STR-148's live verification: telemetry-aggregates'
backfill.py recomputes each store's raw readings against the *current*
snapshot of store_product_thresholds, with no notion of when a pairing
started — so a product added to a store mid-stream got every reading
from earlier in the hour (recorded before it was ever associated)
retroactively folded into its aggregate. `updated_at` couldn't fix this
on its own since it also bumps on ProductThresholdUpdated (a max_temp
change on an already-long-tracked pair), so a dedicated
insert-only-never-updated column is needed.

Existing rows get `now()` as a best-effort default — there's no way to
recover the real historical tracked-since moment for pairs that already
existed before this migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b32c18af9ad'
down_revision: Union[str, None] = '69ff8539f688'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'store_product_thresholds',
        sa.Column('tracked_since', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    # New role from the previous migration also needs SELECT on this
    # column — GRANT SELECT on a table covers all its columns including
    # ones added later, so no additional grant is needed here. Included as
    # a comment rather than a no-op statement to make that explicit.


def downgrade() -> None:
    op.drop_column('store_product_thresholds', 'tracked_since')
