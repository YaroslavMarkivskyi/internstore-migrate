# ADR 0003: Temporal orchestration for checkout, parallel to the Kafka saga

- Status: Accepted (evaluation path — not a cutover decision)
- Date: 2026-08-07

## Context

ADR 0002 chose choreography over Kafka for the Orders/Inventory reservation
saga, and that's implemented and working for the forward path
(`OrderCreated → StockReserved/StockReservationFailed → PaymentConfirmed →
StockDecremented`, plus `ReservationExpired`). Architecture review surfaced
a real gap in that design that choreography doesn't have a good answer
for: if a **compensation** step itself fails repeatedly — e.g. Inventory is
down when Orders needs to release reserved stock after a payment failure —
there's no single place to see that the saga is stuck, retry it
systematically, or escalate to a human. The failure is scattered across
whichever service's consumer loop last logged an exception, and a stray
malformed message on the topic can silently wedge a consumer for good (see
STR-133, referenced in `orders/kafka.py`).

STR-139 introduces Temporal as a workflow orchestrator for checkout
specifically — explicit, observable orchestration for one saga — to
evaluate against the choreography approach before deciding whether to fully
cut over. It is **not** a replacement: the existing `/checkout` and its
Kafka-choreographed saga are untouched, and both run side by side behind
different endpoints (`/checkout` vs `/checkout/v2`) during evaluation.
Kafka itself isn't going anywhere either way — it stays for what ADR 0002
chose it for: async fan-out to Notifications/Telemetry/Chat, and the
existing saga's forward path.

## Decision

Add **Temporal** as a second, narrowly-scoped coordination mechanism,
used only for the checkout flow's explicit orchestration
(`services/checkout-workflow`'s `CheckoutWorkflow`), while every other
event-driven interaction in the system continues to use Kafka choreography
exactly as ADR 0002 describes.

### Options considered

| Option | Verdict | Why |
|---|---|---|
| Temporal, parallel path | **Chosen** | Workflow state is persisted (Cloud SQL/`temporal-db`), not held in memory — a crashed worker resumes from Temporal's event history instead of losing state. Compensation activities get an independent, unbounded retry policy (`RetryPolicy(maximum_attempts=0)`) distinct from the forward path's bounded retries, and the workflow visibly stays `Running` instead of silently failing. Full execution history (every activity, retry, compensation) is queryable in Temporal Web UI — directly answers the "scattered across service logs" problem. Evaluable in parallel with zero risk to the working choreographed saga. |
| Fix the choreography saga in place (e.g. add a stuck-reservation dashboard, dead-letter topic for failed compensations) | Rejected for this ticket | Would address the same symptom without an orchestrator's actual state machine or execution history — likely more bespoke code (a saga-state table, retry-tracking, a dashboard) to get partway to what Temporal already provides. Not rejected outright: if this evaluation doesn't justify Temporal's operational cost, this is the fallback. |
| Full cutover of the reservation saga to Temporal now | Rejected for this ticket | Skips the evaluation step entirely — replacing a saga already in production use (STR-124) with an unevaluated new orchestrator is exactly the risk this ticket is structured to avoid. A cutover decision is explicitly deferred to after this parallel path has been exercised. |

## What this does NOT cover

Deliberately out of scope for this ticket (see `services/checkout-workflow/README.md`
and the ticket write-up for the full list):

- Full cutover from the Kafka-choreographed reservation saga — this ADR
  adds Temporal as a parallel, evaluable path only.
- OPA/RBAC policy enforcement — only a `check_permission()` placeholder
  stub (always `True`) at each new endpoint's authorization call site.
- Real payment gateway integration — the new Payments service
  (`services/payments`) simulates charge/refund outcomes; no Stripe/etc.
  integration.
- GCP Terraform/IaC for Temporal on GKE Autopilot — this ticket covers
  docker-compose for local dev only; the GKE/Cloud SQL deployment described
  in the ticket is a follow-up.

## Local development

`docker compose up -d` adds, alongside the existing stack:

- `temporal-db` — dedicated Postgres database (`temporal`), separate from
  every domain service's own database.
- `temporal` — `temporalio/auto-setup` image; internal-only, no host port,
  reachable only from other containers (the worker, Orders' Temporal
  client).
- `temporal-ui` — published on its own host port (`8088`), **not** routed
  through nginx — same treatment as MinIO's console and Mailpit's web UI:
  a dev-only operator tool, not a browser-facing domain service.
- `payments` / `payments-db` — the new Payments service.
- `checkout-workflow-worker` — the Temporal worker, its own container
  (independently killable/restartable from any API pod, per the ticket's
  "kill the worker mid-workflow, confirm it resumes" verification step) —
  not co-located with Orders.

New Kafka topic: `ops-events` (`EscalationRequired`, produced by
`checkout-workflow`'s `release_stock` activity once compensation retries
are exhausted, consumed by Notifications for an admin alert) — see
[docs/EVENT_BROKER.md](../EVENT_BROKER.md).

[scripts/test-temporal-saga.sh](../../scripts/test-temporal-saga.sh) drives
both the happy path and the payment-failure/compensation path through
`/checkout/v2` and asserts the expected activity sequence via the Temporal
CLI.

## Consequences

- A second stateful coordination system to operate locally (Temporal +
  its own Postgres) alongside Kafka — evaluation cost, paid up front so a
  future cutover decision is informed rather than speculative.
- Checkout now has two parallel code paths (`/checkout` and
  `/checkout/v2`) with independent implementations of overlapping domain
  logic (order creation, stock reservation, payment). Deliberate for the
  evaluation period; a real maintenance cost if evaluation drags on
  without a cutover decision either way.
- `services/checkout-workflow` and `services/payments` are new
  independent deployables (own `pyproject.toml`/Dockerfile/tests, per this
  repo's per-service convention) — more services to build/deploy, not
  folded into Orders.
- `services/inventory` gained two small synchronous endpoints
  (`POST /stocks/reserve`, `POST /stocks/release`) purely for
  `checkout-workflow`'s activities to call directly — deliberately
  choreography-free (no outbox event published) so the Kafka-based saga's
  own consumers never react to a `/checkout/v2` order they weren't
  involved in.
