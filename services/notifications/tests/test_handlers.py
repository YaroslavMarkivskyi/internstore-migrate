import pytest

from notifications.consumers.handlers import make_dispatch
from notifications.dedup import DedupCache


class FakeMailer:
    def __init__(self, raises: Exception | None = None) -> None:
        self.sent: list[tuple[str, str, str]] = []
        self._raises = raises

    async def send_email(self, to: str, subject: str, body: str) -> None:
        if self._raises is not None:
            raise self._raises
        self.sent.append((to, subject, body))


def _envelope(event_type: str, event_id: str = "evt-1", **payload) -> dict:
    return {"event_id": event_id, "event_type": event_type, "payload": payload}


async def test_unknown_event_type_is_ignored():
    mailer = FakeMailer()
    dispatch = make_dispatch(mailer, DedupCache(60, 100))

    await dispatch(_envelope("OrderCreated", order_id="1"))

    assert mailer.sent == []


async def test_known_event_type_sends_email():
    mailer = FakeMailer()
    dispatch = make_dispatch(mailer, DedupCache(60, 100))

    await dispatch(
        _envelope("PaymentConfirmed", order_id="1", contact_email="jane@example.com", contact_name="Jane", items=[])
    )

    assert len(mailer.sent) == 1
    assert mailer.sent[0][0] == "jane@example.com"


async def test_duplicate_event_id_sends_only_once():
    mailer = FakeMailer()
    dedup = DedupCache(60, 100)
    dispatch = make_dispatch(mailer, dedup)
    envelope = _envelope(
        "PaymentConfirmed", event_id="evt-dup", order_id="1", contact_email="jane@example.com", contact_name="Jane", items=[]
    )

    await dispatch(envelope)
    await dispatch(envelope)

    assert len(mailer.sent) == 1


async def test_failed_send_leaves_event_unmarked_so_redelivery_retries():
    mailer = FakeMailer(raises=ConnectionError("smtp down"))
    dedup = DedupCache(60, 100)
    dispatch = make_dispatch(mailer, dedup)
    envelope = _envelope(
        "PaymentConfirmed", event_id="evt-2", order_id="1", contact_email="jane@example.com", contact_name="Jane", items=[]
    )

    with pytest.raises(ConnectionError):
        await dispatch(envelope)

    assert dedup.seen("evt-2") is False  # not marked — a retry should actually resend
