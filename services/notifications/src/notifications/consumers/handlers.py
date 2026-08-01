from collections.abc import Awaitable, Callable

from notifications import templates
from notifications.dedup import DedupCache
from notifications.mailer import Mailer

TemplateBuilder = Callable[[dict], tuple[str, str, str]]

HANDLERS: dict[str, TemplateBuilder] = {
    "PaymentConfirmed": templates.payment_confirmed,
    "OrderRejected": templates.order_rejected,
    "OrderCancelled": templates.order_cancelled,
    "TemperatureThresholdViolated": templates.temperature_threshold_violated,
    "UnreadMessageReceived": templates.unread_message_received,
}


def make_dispatch(mailer: Mailer, dedup: DedupCache) -> Callable[[dict], Awaitable[None]]:
    async def dispatch(envelope: dict) -> None:
        build = HANDLERS.get(envelope.get("event_type", ""))
        if build is None:
            # Other event types on these topics (OrderCreated, StockReserved,
            # ...) aren't ours to react to — ignore rather than error.
            return

        event_id = envelope["event_id"]
        if dedup.seen(event_id):
            return

        to, subject, body = build(envelope.get("payload", {}))
        await mailer.send_email(to, subject, body)
        # Only mark after a successful send: a send that raises (retries
        # exhausted) leaves this event unmarked, so a genuine redelivery
        # retries the send instead of being skipped as a false duplicate.
        dedup.mark(event_id)

    return dispatch
