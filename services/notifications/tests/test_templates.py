from notifications import templates


def test_payment_confirmed_builds_recipient_subject_and_body():
    payload = {
        "order_id": "order-1",
        "contact_email": "jane@example.com",
        "contact_name": "Jane Doe",
        "items": [{"product_id": "prod-1", "quantity": 2}],
    }

    to, subject, body = templates.payment_confirmed(payload)

    assert to == "jane@example.com"
    assert "order-1" in subject
    assert "Jane Doe" in body
    assert "prod-1" in body
    assert "2" in body


def test_order_rejected_builds_recipient_and_subject():
    payload = {"order_id": "order-2", "contact_email": "jane@example.com", "contact_name": "Jane Doe"}

    to, subject, body = templates.order_rejected(payload)

    assert to == "jane@example.com"
    assert "order-2" in subject
    assert "out of stock" in body.lower()


def test_order_cancelled_builds_recipient_and_subject():
    payload = {"order_id": "order-3", "contact_email": "jane@example.com", "contact_name": "Jane Doe"}

    to, subject, body = templates.order_cancelled(payload)

    assert to == "jane@example.com"
    assert "order-3" in subject
    assert "cancelled" in body.lower()


def test_temperature_threshold_violated_falls_back_to_ops_email():
    to, subject, body = templates.temperature_threshold_violated({"stock_id": "stock-1", "temperature": 12.5})

    assert to == templates.OPS_NOTIFICATION_EMAIL
    assert "stock-1" in subject
    assert "12.5" in body


def test_temperature_threshold_violated_uses_notify_email_if_present():
    to, _, _ = templates.temperature_threshold_violated({"stock_id": "s", "temperature": 1, "notify_email": "ops2@example.com"})

    assert to == "ops2@example.com"


def test_unread_message_received_falls_back_to_ops_email():
    to, subject, body = templates.unread_message_received({"sender_name": "Bob"})

    assert to == templates.OPS_NOTIFICATION_EMAIL
    assert "Bob" in body


def test_admin_requested_falls_back_to_ops_email():
    to, subject, body = templates.admin_requested({"room_id": "room_1"})

    assert to == templates.OPS_NOTIFICATION_EMAIL
    assert "room_1" in subject
    assert "room_1" in body


def test_escalation_required_falls_back_to_ops_email():
    to, subject, body = templates.escalation_required(
        {"workflow_id": "checkout-abc", "order_id": "order-1", "reason": "release_stock retries exhausted"}
    )

    assert to == templates.OPS_NOTIFICATION_EMAIL
    assert "checkout-abc" in subject
    assert "checkout-abc" in body
    assert "order-1" in body
    assert "release_stock retries exhausted" in body
