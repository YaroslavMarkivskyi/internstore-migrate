"""Pure transform logic for the STR-149 stock_events backfill data
migration (see migrations/versions/85cc420998d1_backfill_stock_events.py).

Factored out of the Alembic migration script so it can be exercised
directly in tests (test_migration.py) without needing real Alembic
machinery -- `op.get_bind()`/`op.execute()` only work inside an actual
`alembic upgrade` run, but the row-to-event transform itself is plain,
DB-agnostic Python with no dependency on `alembic.op`.
"""

import uuid
from datetime import datetime, timezone

from inventory.events import STOCK_ITEM_CREATED, STOCK_RESERVED, compute_aggregate_id


def build_backfill_events(
    stock_items: list[dict],
    outstanding_reservations_by_item_id: dict[uuid.UUID, list[tuple[int, uuid.UUID]]],
    now: str | None = None,
) -> list[dict]:
    """`stock_items`: `[{"id", "stock_id", "product_id", "quantity"}, ...]`
    -- one dict per existing `stock_items` row. `outstanding_reservations_
    by_item_id`: stock_item id -> `[(quantity, order_id), ...]` for every
    `RESERVED` `reservation_items` row referencing that stock_item, read
    from Inventory's own `reservations`/`reservation_items` tables (see
    the migration's docstring for why this doesn't cross-reference Orders).

    Returns a flat, sequence_number-ordered list of `stock_events` row
    dicts (`id`, `aggregate_id`, `event_type`, `payload`,
    `sequence_number`), ready to insert: one `StockItemCreated` per item
    (using its current `quantity` as `initial_quantity`), followed by one
    `StockReserved` per outstanding reservation against it. Replaying
    these for a given aggregate reproduces that row's pre-migration
    `quantity`/`reserved_quantity` exactly (see test_migration.py).
    """
    now = now or datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []

    for item in stock_items:
        aggregate_id = compute_aggregate_id(item["stock_id"], item["product_id"])
        seq = 1
        rows.append(
            {
                "id": uuid.uuid4(),
                "aggregate_id": aggregate_id,
                "event_type": STOCK_ITEM_CREATED,
                "payload": {
                    "aggregate_id": str(aggregate_id),
                    "stock_id": str(item["stock_id"]),
                    "product_id": str(item["product_id"]),
                    "initial_quantity": item["quantity"],
                    "created_at": now,
                },
                "sequence_number": seq,
            }
        )
        seq += 1

        for quantity, order_id in outstanding_reservations_by_item_id.get(item["id"], []):
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "aggregate_id": aggregate_id,
                    "event_type": STOCK_RESERVED,
                    "payload": {
                        "aggregate_id": str(aggregate_id),
                        "stock_id": str(item["stock_id"]),
                        "product_id": str(item["product_id"]),
                        "quantity": quantity,
                        "order_id": str(order_id),
                        "reserved_at": now,
                    },
                    "sequence_number": seq,
                }
            )
            seq += 1

    return rows
