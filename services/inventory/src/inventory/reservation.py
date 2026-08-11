"""STR-149: reservation logic itself moved into commands.py (build_reserve/
build_release/build_consume, plus the retrying reserve/release/consume
wrappers) so it can go through the event-sourced append+projection path
instead of mutating `StockItem.quantity`/`reserved_quantity` directly.

This module now only re-exports the pieces existing callers import by
name, so `consumers/order_events.py`, `reservation_expiry.py`, and
`routers/stocks.py` don't need their import statements rewritten. New code
should import from `inventory.commands` directly.
"""

from inventory.commands import (
    build_consume as build_consume,
    build_reserve as build_reserve,
    build_release as build_release,
    consume as consume,
    release as release,
    reserve as reserve,
)

__all__ = ["build_consume", "build_reserve", "build_release", "consume", "release", "reserve"]
