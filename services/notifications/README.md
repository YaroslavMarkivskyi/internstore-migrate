# notifications

Event-driven email for InternStore. Fourth domain service, and the first
pure event consumer: no Gateway route, no synchronous callers, no callees.
It only reacts to events already flowing through Kafka and sends email via
Mailpit — see the dev-only gap note below.

## Frontend's admin notification bell is disabled

`frontend/src/hooks/useNotifications.ts` opens an SSE connection to
`{SERVER_URL}notifications/live/` for a live admin notification bell —
inherited from `frontend`'s upstream source, which targets a different
backend that has such an endpoint. This service has no HTTP interface at
all (see above), so that path 404s/405s through nginx (no
`/api/notifications/` location exists — see
[nginx/nginx.conf](../../nginx/nginx.conf)). `frontend/src/App.tsx` passes
`enabled: false` to the hook to stop it retrying against a route that will
never exist without a real architecture change here (a synchronous
HTTP/SSE endpoint added to this service, plus a Gateway route for it).

## What it does

Subscribes to all four topics documented in
[docs/EVENT_BROKER.md](../../docs/EVENT_BROKER.md) — `order-events`,
`inventory-events`, `telemetry-events`, `chat-events` — and dispatches on
each message's `event_type`, not on which topic it arrived on (the
subscription is per-topic; the handler lookup isn't). That means a topic
with no producer yet (`telemetry-events`/`chat-events` — Telemetry and Chat
don't exist yet) just never yields a message, and the consumer for it sits
idle rather than erroring.

Handled today:

- `PaymentConfirmed` (from `order-events`) → payment confirmation email.
- `OrderRejected` (from `order-events`) → "couldn't be fulfilled" email.
- `OrderCancelled` (from `order-events`) → "reservation expired, order
  cancelled" email.

Wired up but inert until their producers exist:

- `TemperatureThresholdViolated` (from `telemetry-events`).
- `UnreadMessageReceived` (from `chat-events`).

Both of the above use a best-guess payload shape (see
[src/notifications/templates.py](src/notifications/templates.py)) — revisit
once Telemetry/Chat's real event contracts land.

Any other event type seen on these topics (`OrderCreated`, `StockReserved`,
...) is silently ignored — Notifications doesn't own a reaction to them.

## Why `OrderRejected`/`OrderCancelled` had to be added to Orders

Orders' existing inventory-events consumer
(`services/orders/src/orders/consumers/inventory_events.py`) used to just
flip `Order.status` on `StockReservationFailed`/`ReservationExpired` and
stop — it never published anything onward. Since those Inventory-origin
events only carry `order_id` (Inventory has no contact info), and
Notifications must stay a pure consumer (no synchronous call back to
Orders to fetch it), the only clean fix was for Orders itself to publish
`OrderRejected`/`OrderCancelled` on `order-events`, carrying
`contact_email`/`contact_name`, whenever its guarded transition actually
fires. Same for `OrderCreated`/`PaymentConfirmed`, which didn't carry
contact info either until now.

## No database

Notifications is stateless by design — a consumer reads an event, sends an
email, commits its offset. There's no business state worth persisting, so
unlike Catalog/Inventory/Orders there's no Postgres database and no
Alembic migrations here.

## Idempotency: in-memory TTL cache, not a `processed_events` table

Inventory's idempotency ledger (`processed_events`, a real table) isn't an
option here — there's no database. Instead,
[src/notifications/dedup.py](src/notifications/dedup.py) is a hand-rolled
in-memory `event_id -> expires_at` cache with a max size and TTL.

This is a deliberate, weaker guarantee than Inventory's, and the trade-off
is accepted rather than hidden: the cache is **per-process and
non-persistent** — a redelivery arriving after this service restarts (or
once an entry has aged past its TTL) will send a duplicate email. That's
fine here because the failure mode is "an email arrives twice," not
corrupted business state — a materially different severity than Inventory
double-reserving stock, which is why that side gets a real table and this
one doesn't.

An event is only marked processed *after* its email successfully sends
(see [src/notifications/consumers/handlers.py](src/notifications/consumers/handlers.py)) —
a send that exhausts its SMTP retries and raises leaves the event
unmarked, so a genuine Kafka redelivery retries the send rather than being
incorrectly skipped as a duplicate.

## Mailpit is a dev-only stub

Email goes through [Mailpit](https://mailpit.axllent.org/), a local SMTP
server with a web UI (`http://localhost:8025`) and REST API
(`GET /api/v1/messages`) — no real inbox is ever reached, no real provider
API keys needed for local dev/CI. Documented as an accepted, dev-only gap
alongside Kafka's missing auth/ACL and `check-availability`'s
`reserved_quantity` blindness — see
[docs/EVENT_BROKER.md](../../docs/EVENT_BROKER.md#known-accepted-gaps-dev-only-stage).
Swapping in a real provider (SES/Resend/SendGrid/...) is a separate,
later task, once there's a prod/AWS configuration to wire it into — the
SMTP client itself ([src/notifications/mailer.py](src/notifications/mailer.py))
doesn't know it's talking to a stub; it's just a different hostname/port.

## SMTP retry

`Mailer.send_email` retries a connection failure 3 times with exponential
backoff (1s/2s/4s) before raising. If a caller lets that exception
propagate out of the Kafka dispatch, the consumer loop
([src/notifications/kafka.py](src/notifications/kafka.py)) skips its offset
commit — a natural at-least-once redelivery, the same principle as the
Orders/Inventory outbox pattern but simpler here: there's no separate DB
write that could get out of sync with the send, so no outbox is needed —
"commit only after a successful send" is the whole story.

## Local dev without Docker

```bash
cd services/notifications
cp .env.example .env   # point KAFKA_BOOTSTRAP_SERVERS/SMTP_HOST at a running Kafka/Mailpit
uv sync
uv run uvicorn notifications.main:create_app --factory --reload
```

## End-to-end verification

[scripts/test-notifications-saga.sh](../../scripts/test-notifications-saga.sh)
drives a real checkout → pay through Orders' gateway routes, then polls
Mailpit's REST API until the expected email shows up — proves the whole
chain (`PaymentConfirmed` → Notifications consumer → Mailpit) through the
real broker and a real SMTP hop, not just visually in Mailpit's UI.
