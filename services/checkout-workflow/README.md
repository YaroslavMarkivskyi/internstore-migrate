# checkout-workflow

Temporal orchestration for checkout (STR-139) — a parallel, evaluable
alternative to Orders' existing Kafka-choreographed reservation saga
(STR-124, [docs/adr/0002](../../docs/adr/0002-event-broker-kafka.md)), not a
replacement. Orders' `/checkout` and its Kafka saga are completely
untouched; this package backs the additive `POST /checkout/v2` instead
(see [services/orders/src/orders/routers/checkout_v2.py](../orders/src/orders/routers/checkout_v2.py)).

Standalone service on purpose — not nested under `services/orders/` — so
its Temporal-specific dependency (`temporalio`) and independently
scalable/restartable worker process don't get pulled into Orders' own
deployable. See [docs/adr/0003-temporal-checkout-orchestration.md](../../docs/adr/0003-temporal-checkout-orchestration.md)
for the full rationale.

## Why Temporal here

- Workflow state is persisted (Cloud SQL / local `temporal-db` Postgres),
  not held in memory — a crashed worker pod resumes exactly where it left
  off from Temporal's event history, no phantom state.
- Compensation (`release_stock`) gets an unbounded retry policy
  (`RetryPolicy(maximum_attempts=0)`) independent of the forward path's
  bounded retries, and the workflow visibly stays in `Running` state
  instead of silently failing — see `docs/EVENT_BROKER.md`'s escalation
  paragraph and `mark_compensation_resolved` below.
- Full execution history (every activity call, retry, and compensation) is
  queryable in the Temporal Web UI — see docker-compose's `temporal-ui`
  service.

## Structure

- `workflows.py` — `CheckoutWorkflow`: reserve_stock → create_order →
  charge_payment → update_order_status("paid") → publish_order_confirmed,
  with a reverse-order compensation chain (release_stock, then
  mark_order_rejected) on any `ActivityError` from the create/charge/update
  steps. `reserve_stock` itself is outside that try/except — nothing's
  been reserved yet if it fails, so there's nothing to compensate.
- `activities.py` — one function per activity, each a thin `httpx` call
  into Inventory/Orders/Payments with a freshly-minted internal token (no
  inbound request to forward from inside an activity). Every activity's
  docstring names the specific idempotency mechanism it relies on on the
  target service's side — verified, not assumed, per the ticket.
- Escalation: `release_stock` publishes `EscalationRequired` onto a new
  `ops-events` Kafka topic once its Temporal attempt count first crosses
  `Settings.escalation_attempt_threshold` (default 10). Notifications
  consumes it and sends an admin alert carrying the `workflow_id`.
- `CheckoutWorkflow.mark_compensation_resolved` — a `@workflow.signal`. An
  admin who resolved compensation manually (e.g. released stock directly
  in Inventory's DB) signals this instead of waiting for the still-
  unboundedly-retrying `release_stock` activity to succeed on its own; the
  workflow races the activity against the signal and finishes as soon as
  either resolves.
- `worker.py` — connects to Temporal Server, registers the workflow and
  every activity, polls the task queue. This is the
  `checkout-workflow-worker` compose service's entrypoint — its own
  container, independently killable/restartable from Orders' API pod (see
  the root README's Temporal verification steps).

## Tests

```
uv run pytest
```

- `test_activities.py` — each activity against a faked `httpx.AsyncClient`
  (no DI seam for activities the way FastAPI routes have, so the fake is
  monkeypatched in directly) and a faked Kafka producer; includes the
  escalation-threshold behavior.
- `test_workflow_happy_path.py` / `test_workflow_payment_failure.py` /
  `test_workflow_compensation_failure.py` — `temporalio.testing.WorkflowEnvironment`'s
  time-skipping test server (no real Temporal deployment needed, downloads
  a test-server binary on first use), all activities replaced with fakes
  registered under the same names. The compensation-failure test asserts
  the workflow is still `RUNNING` after several genuine (wall-clock)
  retry cycles against an always-failing `release_stock`, then signals
  `mark_compensation_resolved` and asserts the workflow finishes anyway.

## Via docker compose

```
docker compose up -d --build temporal temporal-db temporal-ui payments checkout-workflow-worker
```

No FastAPI app, no host port — this container is a pure Temporal task
queue poller, same shape as Orders'/Inventory's outbox worker but split
into its own container so it can be killed/restarted independently (see
the ticket's "kill the worker mid-workflow" verification step).
