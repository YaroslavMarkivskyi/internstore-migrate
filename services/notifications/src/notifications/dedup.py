import time


class DedupCache:
    """In-memory idempotency ledger, keyed by event_id.

    Notifications has no database — it's deliberately stateless (see
    services/notifications/README.md). Inventory's `processed_events` table
    isn't an option here, so this hand-rolled TTL cache is the whole
    idempotency story: a redelivered event_id within `ttl_seconds` is
    skipped, exactly like Inventory's ledger, but with a real trade-off
    that's accepted rather than hidden — this cache is per-process and
    non-persistent. A redelivery arriving *after a restart* (or once an
    entry has aged out) will send a duplicate email. That's fine here
    because the failure mode is "an email arrives twice," not corrupted
    business state — a materially different severity than Inventory
    double-reserving stock, which is why that side gets a real table and
    this one doesn't.

    `seen()` only checks; callers must call `mark()` themselves, and only
    after the side effect (the actual send) has succeeded — see
    consumers/handlers.py. That ordering means a send that fails and later
    gets redelivered is retried, not incorrectly treated as a duplicate.
    """

    def __init__(self, ttl_seconds: float, max_size: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_size = max_size
        self._entries: dict[str, float] = {}  # event_id -> expires_at

    def _evict_expired(self, now: float) -> None:
        expired = [event_id for event_id, expires_at in self._entries.items() if expires_at <= now]
        for event_id in expired:
            del self._entries[event_id]

    def seen(self, event_id: str) -> bool:
        now = time.monotonic()
        self._evict_expired(now)
        return event_id in self._entries

    def mark(self, event_id: str) -> None:
        now = time.monotonic()
        if len(self._entries) >= self._max_size:
            # Oldest-expiry eviction: drop the entry closest to aging out
            # anyway rather than growing unbounded.
            oldest_id = min(self._entries, key=self._entries.get)  # type: ignore[arg-type]
            del self._entries[oldest_id]
        self._entries[event_id] = now + self._ttl_seconds
