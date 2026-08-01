"""Plain-text (to, subject, body) builders, one per event type. No
HTML/design layer — explicitly out of scope for this ticket."""

# Fallback recipient for events that aren't about a specific customer
# (e.g. an ops/telemetry alert). Best-guess pending Telemetry/Chat's real
# contracts — see the two builders below.
OPS_NOTIFICATION_EMAIL = "ops@internstore.local"


def payment_confirmed(payload: dict) -> tuple[str, str, str]:
    order_id = payload["order_id"]
    items = payload.get("items", [])
    lines = "\n".join(f"  - {item['product_id']}: {item['quantity']}" for item in items)
    body = (
        f"Hi {payload['contact_name']},\n\n"
        f"We've received your payment for order {order_id}. Thank you!\n\n"
        f"Items:\n{lines}\n"
    )
    return payload["contact_email"], f"Payment confirmed for order {order_id}", body


def order_rejected(payload: dict) -> tuple[str, str, str]:
    order_id = payload["order_id"]
    body = (
        f"Hi {payload['contact_name']},\n\n"
        f"Unfortunately order {order_id} couldn't be fulfilled — one or more items were "
        f"out of stock by the time we tried to reserve them. No payment was taken.\n"
    )
    return payload["contact_email"], f"Order {order_id} could not be fulfilled", body


def order_cancelled(payload: dict) -> tuple[str, str, str]:
    order_id = payload["order_id"]
    body = (
        f"Hi {payload['contact_name']},\n\n"
        f"Your reservation for order {order_id} has expired before payment was received, "
        f"so the order has been cancelled and the stock released. Feel free to re-order "
        f"if you'd still like these items.\n"
    )
    return payload["contact_email"], f"Order {order_id} was cancelled (reservation expired)", body


def temperature_threshold_violated(payload: dict) -> tuple[str, str, str]:
    # Telemetry doesn't exist yet — this is a best-guess shape for its
    # eventual payload, kept intentionally simple. Revisit once Telemetry's
    # real contract lands.
    stock_id = payload.get("stock_id", "unknown")
    temperature = payload.get("temperature", "unknown")
    to = payload.get("notify_email", OPS_NOTIFICATION_EMAIL)
    body = f"Stock {stock_id} has exceeded its safe temperature threshold (reading: {temperature}).\n"
    return to, f"Temperature threshold violated for stock {stock_id}", body


def unread_message_received(payload: dict) -> tuple[str, str, str]:
    # Chat doesn't exist yet — same caveat as temperature_threshold_violated.
    to = payload.get("recipient_email", OPS_NOTIFICATION_EMAIL)
    sender = payload.get("sender_name", "someone")
    body = f"You have an unread message from {sender}.\n"
    return to, "You have a new unread message", body
