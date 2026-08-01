from sqlalchemy.ext.asyncio import AsyncSession

from orders.models import OutboxEvent


def add_outbox_event(session: AsyncSession, event_type: str, payload: dict) -> None:
    """Stages an outbox row in the caller's existing transaction. Does not
    commit — the caller's own commit makes the domain change and this event
    durable atomically."""
    session.add(OutboxEvent(event_type=event_type, payload=payload))
