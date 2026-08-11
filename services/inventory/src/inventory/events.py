"""Event type constants and the aggregate identity scheme for Inventory's
event-sourced `(stock_id, product_id)` aggregate.

See services/inventory/README.md's "Event sourcing" section for the full
design rationale: why `stock_events` (not `stock_items`) is the source of
truth, why the projection is synchronous, and why snapshots are scoped the
way they are.
"""

import uuid

# Fixed once, committed as a literal -- never re-derive at runtime, never
# change. Any caller (a router, the projector, the data-backfill migration)
# that knows a (stock_id, product_id) pair can compute the same
# aggregate_id independently, with no lookup/registry table and no
# round-trip. This is a narrow, deliberate deviation from the rest of this
# repo's plain `uuid.uuid4()` convention -- it's the only place a stable ID
# needs to be derived *from* two other UUIDs rather than minted fresh.
AGGREGATE_NAMESPACE = uuid.UUID("2b6f9a3e-2c1d-4b8a-9f2e-7a1c5d9e3b6f")


def compute_aggregate_id(stock_id: uuid.UUID, product_id: uuid.UUID) -> uuid.UUID:
    """The stream identity for the `(stock_id, product_id)` aggregate.
    Deterministic: same inputs always produce the same aggregate_id, so
    `stock_events.aggregate_id` (a single UUID column, not a composite key)
    can address a stream without a lookup table. A `stock_items` row and its
    `stock_events` stream always agree on this value.
    """
    return uuid.uuid5(AGGREGATE_NAMESPACE, f"{stock_id}:{product_id}")


# Event type strings stored in stock_events.event_type. Plain string
# constants (not a DB enum) to match the rest of this repo's outbox
# event_type convention (see models.OutboxEvent.event_type).
STOCK_ITEM_CREATED = "StockItemCreated"
ITEM_RECEIVED = "ItemReceived"
ITEM_MOVED_OUT = "ItemMovedOut"
ITEM_MOVED_IN = "ItemMovedIn"
STOCK_RESERVED = "StockReserved"
STOCK_RELEASED = "StockReleased"
STOCK_CONSUMED = "StockConsumed"
STOCK_ITEM_QUANTITY_SET = "StockItemQuantitySet"
STOCK_ITEM_REMOVED = "StockItemRemoved"
MARKED_UNAVAILABLE = "MarkedUnavailable"
MARKED_AVAILABLE = "MarkedAvailable"

# The exhaustive set apply_event (projector.py) branches on. STR-149 event
# list, reconciled against the actual current endpoint/consumer set -- see
# README for the documented discrepancies from the ticket's original list
# (ItemMoved split into two directional events; StockItemQuantitySet and
# StockItemRemoved added to cover admin endpoints the ticket's list didn't
# mention; MarkedAvailable backed by a new admin endpoint since nothing
# previously cleared is_unavailable).
ALL_EVENT_TYPES = frozenset(
    {
        STOCK_ITEM_CREATED,
        ITEM_RECEIVED,
        ITEM_MOVED_OUT,
        ITEM_MOVED_IN,
        STOCK_RESERVED,
        STOCK_RELEASED,
        STOCK_CONSUMED,
        STOCK_ITEM_QUANTITY_SET,
        STOCK_ITEM_REMOVED,
        MARKED_UNAVAILABLE,
        MARKED_AVAILABLE,
    }
)
