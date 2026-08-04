from sqlalchemy.ext.asyncio import AsyncSession

from orders.models import Order, OrderStatus
from orders.outbox import add_outbox_event


class OrderNotPayableError(Exception):
    """Raised when an order isn't in a state that can transition to paid."""


def mark_order_paid(session: AsyncSession, order: Order) -> None:
    """Shared by the customer-facing /pay endpoint, the admin cash-on-delivery
    confirm endpoint, and the Stripe webhook handler -- all three land here
    so the status guard and the PaymentConfirmed outbox event (consumed by
    Notifications) stay in one place instead of drifting across three
    copies. Caller owns the session/commit, same convention as the rest of
    this service's route handlers -- order.items must already be loaded
    (selectinload) before calling this."""
    if order.status != OrderStatus.PENDING:
        raise OrderNotPayableError(f"Order must be pending to pay, currently {order.status.value}")

    order.status = OrderStatus.PAID
    add_outbox_event(
        session,
        "PaymentConfirmed",
        {
            "order_id": str(order.id),
            "contact_email": order.contact_email,
            "contact_name": order.contact_name,
            "items": [{"product_id": str(item.product_id), "quantity": item.quantity} for item in order.items],
        },
    )
