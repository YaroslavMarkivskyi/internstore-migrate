"""STR-149: one-time data migration converting existing stock_items rows
into an initial StockItemCreated event per aggregate, plus a synthetic
StockReserved event per currently-outstanding (status='reserved')
reservation -- so replaying stock_events reproduces stock_items' current
quantity/reserved_quantity exactly for every row (see test_migration.py).

Self-contained within Inventory's own database: outstanding reservations
are read from Inventory's own `reservations`/`reservation_items` tables
(status='reserved'), NOT by cross-referencing Orders' database -- Orders
is out of scope for this migration (no change to its read contracts) and
Inventory's own Reservation rows are already the authoritative record of
what Inventory itself considers outstanding at cutover time. (This
corrects the ticket's original instruction to "cross-reference Orders'
Pending orders" -- see README.md's "Corrections to the ticket's
assumptions".)

stock_items itself is untouched by this migration -- it already holds the
correct current projection; this migration only backfills the event log
underneath it, so going live afterwards, the projector finds and updates
these same rows in place (same ids) rather than re-creating them. Code
cutover (STR-149's routers/commands change) is a separate deploy step;
this migration is safe to run standalone ahead of it.

The row-to-event transform itself lives in `inventory.migration_support.
build_backfill_events` -- a plain, DB-agnostic function with no `alembic.
op` dependency, so it can be exercised directly in test_migration.py
without needing real Alembic machinery. This script's job is only to read
rows via `op.get_bind()` and write the transform's output back.

A one-time Python data transform, not pure SQL DDL -- see
services/telemetry/migrations/versions/69ff8539f688_add_telemetry_
aggregates_readonly_role.py for the closest prior structural template
(rich docstring-context + op.execute), though that one is DDL and this one
is a genuine row-by-row read/transform/insert.

Revision ID: 85cc420998d1
Revises: 99d45f76e7ae
Create Date: 2026-08-11 00:00:01.000000

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from inventory.migration_support import build_backfill_events


# revision identifiers, used by Alembic.
revision: str = '85cc420998d1'
down_revision: Union[str, None] = '99d45f76e7ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


stock_items_table = sa.table(
    'stock_items',
    sa.column('id', sa.Uuid()),
    sa.column('stock_id', sa.Uuid()),
    sa.column('product_id', sa.Uuid()),
    sa.column('quantity', sa.Integer()),
)

reservation_items_table = sa.table(
    'reservation_items',
    sa.column('id', sa.Uuid()),
    sa.column('reservation_id', sa.Uuid()),
    sa.column('stock_item_id', sa.Uuid()),
    sa.column('quantity', sa.Integer()),
)

reservations_table = sa.table(
    'reservations',
    sa.column('id', sa.Uuid()),
    sa.column('order_id', sa.Uuid()),
    sa.column('status', sa.String()),
)

stock_events_table = sa.table(
    'stock_events',
    sa.column('id', sa.Uuid()),
    sa.column('aggregate_id', sa.Uuid()),
    sa.column('event_type', sa.String()),
    sa.column('payload', sa.JSON()),
    sa.column('sequence_number', sa.BigInteger()),
)


def upgrade() -> None:
    bind = op.get_bind()

    items = [dict(row) for row in bind.execute(sa.select(stock_items_table)).mappings().all()]

    outstanding_rows = bind.execute(
        sa.select(reservation_items_table.c.stock_item_id, reservation_items_table.c.quantity, reservations_table.c.order_id)
        .select_from(
            reservation_items_table.join(
                reservations_table, reservation_items_table.c.reservation_id == reservations_table.c.id
            )
        )
        .where(reservations_table.c.status == 'reserved')
    ).all()

    outstanding_by_item_id: dict[uuid.UUID, list[tuple[int, uuid.UUID]]] = {}
    for stock_item_id, quantity, order_id in outstanding_rows:
        outstanding_by_item_id.setdefault(stock_item_id, []).append((quantity, order_id))

    event_rows = build_backfill_events(items, outstanding_by_item_id)

    if event_rows:
        bind.execute(stock_events_table.insert(), event_rows)


def downgrade() -> None:
    op.execute("DELETE FROM stock_events")
