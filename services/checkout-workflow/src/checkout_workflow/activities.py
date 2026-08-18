import dataclasses
import logging

import httpx
from opentelemetry import metrics
from temporalio import activity

from checkout_workflow.auth import mint_internal_token
from checkout_workflow.config import Settings, load_settings
from checkout_workflow.kafka import KafkaEventProducer
from checkout_workflow.types import CheckoutWorkflowInput

logger = logging.getLogger(__name__)

# STR-158b/STR-142: workflow-level, not activity-level — recorded from the
# two activities that are each workflows.py's sole path to a terminal
# outcome (publish_order_confirmed only runs on the happy path,
# mark_order_rejected only on the compensation path), not from every
# individual activity. get_meter() here is safe to call before
# configure_metrics() runs (worker.py's setup_observability, called after
# this module is imported) — OTel's metrics API returns a proxy that binds
# to the real MeterProvider once one is set, same as trace.get_tracer()
# already relies on elsewhere in this codebase (see mcp_gateway/router.py).
_meter = metrics.get_meter(__name__)
_workflow_outcomes = _meter.create_counter(
    "checkout_workflow_outcomes_total",
    description="CheckoutWorkflow terminal outcomes: confirmed (happy path) vs compensation_triggered.",
)


class ActivityError(Exception):
    """Raised by an activity below on a definite failure (a target service
    responded but said no, not a transport/5xx blip that Temporal's own
    retry policy already handles by raising httpx's exception directly).
    Temporal wraps whatever an activity raises in its own ActivityError on
    the workflow side either way; this class just gives call sites in
    workflows.py something explicit and specific to catch, matching the
    ticket's `except ActivityError` sketch.
    """


def _headers(settings: Settings) -> dict[str, str]:
    return {"X-Internal-Token": mint_internal_token(settings.internal_token_secret)}


def _items_payload(input: CheckoutWorkflowInput) -> list[dict]:
    return [dataclasses.asdict(item) for item in input.items]


@activity.defn
async def reserve_stock(input: CheckoutWorkflowInput) -> dict:
    """Idempotent via Inventory's POST /stocks/reserve, itself idempotent
    on `order_id` (Reservation.order_id's unique constraint — see
    services/inventory/src/inventory/routers/stocks.py). A retried call
    for the same order_id (this activity's forward-path RetryPolicy in
    workflows.py) finds the reservation already made instead of trying —
    and failing, or worse double-reserving — again.

    STR-160b: Inventory's exhausted-retry response for this endpoint
    changed from an uncaught 500 to a handled 409 (real optimistic-
    concurrency contention, not a server fault). Checked, not assumed:
    `resp.raise_for_status()` below raises httpx.HTTPStatusError for
    either status, and this activity's own RetryPolicy(maximum_attempts=3,
    workflows.py) has no `non_retryable_error_types` — Temporal already
    retries this activity the same way regardless of which 4xx/5xx it
    was. No behavior change needed here; the 409 is still a strictly
    better signal for anyone reading activity failure logs (httpx's
    exception message reads "Client error '409'..." instead of "Server
    error '500'...", correctly pointing at contention instead of a bug)."""
    settings = load_settings()
    async with httpx.AsyncClient(timeout=settings.inventory_timeout_seconds) as client:
        resp = await client.post(
            f"{settings.inventory_base_url}/stocks/reserve",
            json={"order_id": input.order_id, "items": _items_payload(input)},
            headers=_headers(settings),
        )
    resp.raise_for_status()
    body = resp.json()
    if body["status"] != "reserved":
        raise ActivityError(f"reserve_stock: {body['status']}")
    return body


@activity.defn
async def release_stock(input: CheckoutWorkflowInput) -> dict:
    """Compensation — CheckoutWorkflow gives this an unbounded RetryPolicy
    (maximum_attempts=0, see workflows.py). Idempotent via Inventory's
    POST /stocks/release: a reservation already released (or one that was
    never made) is a no-op ("not_found"/"released" either way, never an
    error) — safe to retry forever. Escalates once retried past
    `escalation_attempt_threshold` (see _escalate below)."""
    settings = load_settings()
    if activity.info().attempt == settings.escalation_attempt_threshold + 1:
        await _escalate(settings, input, reason="release_stock retries exhausted")

    async with httpx.AsyncClient(timeout=settings.inventory_timeout_seconds) as client:
        resp = await client.post(
            f"{settings.inventory_base_url}/stocks/release",
            json={"order_id": input.order_id},
            headers=_headers(settings),
        )
    resp.raise_for_status()
    return resp.json()


@activity.defn
async def create_order(input: CheckoutWorkflowInput) -> dict:
    """Idempotent via Orders' POST /internal/checkout-workflow/orders,
    keyed by the workflow-supplied `order_id` (a primary-key lookup, not a
    server-generated id — see orders/routers/checkout_v2.py) — a retried
    call returns the already-created order instead of a duplicate."""
    settings = load_settings()
    async with httpx.AsyncClient(timeout=settings.orders_timeout_seconds) as client:
        resp = await client.post(
            f"{settings.orders_base_url}/internal/checkout-workflow/orders",
            json={
                "id": input.order_id,
                "owner_id": input.owner_id,
                "contact_name": input.contact_name,
                "contact_email": input.contact_email,
                "contact_phone": input.contact_phone,
                "payment_method": input.payment_method,
                "items": _items_payload(input),
            },
            headers=_headers(settings),
        )
    resp.raise_for_status()
    return resp.json()


@activity.defn
async def update_order_status(args: dict) -> dict:
    """`args` is `{"order_id": ..., "status": ...}` (see workflows.py —
    used for both the happy path's explicit "paid" transition and, via
    mark_order_rejected below, the compensation path's "rejected").
    Idempotent: Orders' PATCH handler sets the column unconditionally, safe
    to redeliver since checkout-workflow is the sole writer for a
    /checkout/v2 order (no concurrent Kafka consumer racing it the way the
    choreographed saga's guarded transitions have to guard against)."""
    settings = load_settings()
    async with httpx.AsyncClient(timeout=settings.orders_timeout_seconds) as client:
        resp = await client.patch(
            f"{settings.orders_base_url}/internal/checkout-workflow/orders/{args['order_id']}/status",
            json={"status": args["status"]},
            headers=_headers(settings),
        )
    resp.raise_for_status()
    return resp.json()


@activity.defn
async def mark_order_rejected(input: CheckoutWorkflowInput) -> dict:
    """Compensation step — same endpoint/idempotency as update_order_status,
    just a fixed target status."""
    result = await update_order_status({"order_id": input.order_id, "status": "rejected"})
    _workflow_outcomes.add(1, {"outcome": "compensation_triggered"})
    return result


@activity.defn
async def charge_payment(input: CheckoutWorkflowInput) -> dict:
    """Idempotent via Payments' POST /charge, keyed by order_id (see
    services/payments/src/payments/routers/payments.py)."""
    settings = load_settings()
    async with httpx.AsyncClient(timeout=settings.payments_timeout_seconds) as client:
        resp = await client.post(
            f"{settings.payments_base_url}/charge",
            json={"order_id": input.order_id, "amount": input.amount, "payment_method": input.payment_method},
            headers=_headers(settings),
        )
    resp.raise_for_status()
    body = resp.json()
    if body["status"] != "charged":
        raise ActivityError(f"charge_payment: {body['status']}")
    return body


@activity.defn
async def refund_payment(payment_id: str) -> dict:
    """Not on CheckoutWorkflow's current compensation path — a failed
    charge never took money, so there's nothing to refund on that branch.
    Included per the ticket's activity list, for a future step that needs
    to unwind *after* a successful charge. Idempotent via Payments'
    POST /refund, keyed by payment_id."""
    settings = load_settings()
    async with httpx.AsyncClient(timeout=settings.payments_timeout_seconds) as client:
        resp = await client.post(
            f"{settings.payments_base_url}/refund",
            json={"payment_id": payment_id},
            headers=_headers(settings),
        )
    resp.raise_for_status()
    return resp.json()


@activity.defn
async def publish_order_confirmed(input: CheckoutWorkflowInput) -> None:
    """Kafka, not Temporal — async fan-out for Notifications et al., onto
    the same `order-events` topic and envelope shape Orders' own outbox
    already publishes (see orders/kafka.py). Not idempotency-critical the
    way the HTTP activities above are: a redelivered OrderConfirmed is just
    a second notification, not a double write to domain state."""
    settings = load_settings()
    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    await producer.start()
    try:
        await producer.send(
            "order-events",
            "OrderConfirmed",
            {"order_id": input.order_id, "contact_email": input.contact_email, "contact_name": input.contact_name},
        )
    finally:
        await producer.stop()
    _workflow_outcomes.add(1, {"outcome": "confirmed"})


async def _escalate(settings: Settings, input: CheckoutWorkflowInput, reason: str) -> None:
    """STR-139's escalation path: publish once (on the attempt that first
    crosses the threshold, not every attempt after — see the `==` check at
    release_stock's call site) to a new `ops-events` topic. Notifications
    consumes it and sends an admin alert carrying the workflow_id, so a
    human can investigate and resolve compensation manually (e.g. release
    stock directly in Inventory's DB), then call
    CheckoutWorkflow.mark_compensation_resolved (see workflows.py) to let
    the workflow finish instead of retrying release_stock forever."""
    producer = KafkaEventProducer(settings.kafka_bootstrap_servers)
    await producer.start()
    try:
        await producer.send(
            "ops-events",
            "EscalationRequired",
            {
                "workflow_id": activity.info().workflow_id,
                "order_id": input.order_id,
                "reason": reason,
            },
        )
    finally:
        await producer.stop()
