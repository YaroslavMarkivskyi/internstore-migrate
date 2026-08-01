import time

from notifications.dedup import DedupCache


def test_unseen_event_id_is_not_seen():
    cache = DedupCache(ttl_seconds=60, max_size=100)
    assert cache.seen("event-1") is False


def test_marked_event_id_is_seen_until_ttl_expires():
    cache = DedupCache(ttl_seconds=0.05, max_size=100)
    cache.mark("event-1")
    assert cache.seen("event-1") is True

    time.sleep(0.1)
    assert cache.seen("event-1") is False


def test_eviction_when_over_max_size():
    cache = DedupCache(ttl_seconds=60, max_size=2)
    cache.mark("event-1")
    cache.mark("event-2")
    cache.mark("event-3")  # should evict the oldest-expiry entry (event-1)

    assert len(cache._entries) == 2
    assert cache.seen("event-3") is True
    assert cache.seen("event-2") is True
