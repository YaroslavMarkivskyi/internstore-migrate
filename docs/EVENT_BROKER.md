# Event broker (Kafka)

Decision and rationale: [docs/adr/0002-event-broker-kafka.md](adr/0002-event-broker-kafka.md).

## Connecting

| From | Bootstrap servers |
|---|---|
| Other containers on the compose network | `kafka:9092` |
| Host machine (tests, local scripts, CLI tools) | `localhost:29092` |

No authentication configured (`PLAINTEXT` listeners) — dev-only, same trust
model as the rest of the compose stack.

## Topics

One topic per bounded-context event stream. Consumers dispatch on an
`eventType` field in the message payload rather than relying on separate
topics per event type.

| Topic | Events | Producer |
|---|---|---|
| `order-events` | `OrderCreated`, `PaymentConfirmed`, `OrderRejected`, `OrderCancelled` | Orders service |
| `inventory-events` | `StockReserved`, `StockReservationFailed`, `StockDecremented`, `ReservationExpired`, `ItemAdded` | Inventory service |
| `telemetry-events` | `TemperatureThresholdViolated`, `TemperatureNormalized`, `TemperatureRecorded` | Telemetry service |
| `catalog-events` | `ProductThresholdUpdated`, `ProductUpdated`, `ProductDeleted` | Catalog service |
| `chat-events` | `UnreadMessageReceived`, `CustomerMessageSent`, `AdminRequested`, `AIModeEnabled` | Chat service |
| `ops-events` | `EscalationRequired` | checkout-workflow (STR-139) |

All topics: 1 partition, replication factor 1 (single broker, no HA at this
stage). Created automatically by the `kafka-topic-init` compose service on
`docker compose up -d`.

Security (fingerprint/NFC warehouse access control, STR-127) deliberately
has no topic here and no Kafka dependency at all — access control is
synchronous by nature (a door open/close decision can't wait on eventual
consistency), so every auth attempt is written straight to Security's own
DB via `POST /auth/fingerprint` / `POST /auth/nfc`. See
[services/security/README.md](../services/security/README.md).

Notifications consumes all six topics (dispatching on `eventType`, same as
every other consumer here) and is the first pure event consumer in the
system: no Gateway route, no synchronous callers or callees. See
[services/notifications/README.md](../services/notifications/README.md).

`ops-events` (STR-139) is checkout-workflow's escalation channel, not a
domain-service outbox — `services/checkout-workflow`'s `release_stock`
activity (part of the Temporal-orchestrated checkout, parallel to the
reservation saga above) publishes `EscalationRequired` here once its
unbounded compensation retries first cross an attempt threshold, so
Notifications can alert an admin with the stuck workflow's ID. No
transactional outbox backs this publish (checkout-workflow has no
database) — an occasional duplicate/missed alert on a worker crash is an
accepted gap here, unlike the domain services' at-least-once-with-outbox
topics above. See
[services/checkout-workflow/README.md](../services/checkout-workflow/README.md)
and [docs/adr/0003-temporal-checkout-orchestration.md](adr/0003-temporal-checkout-orchestration.md).

AI Assistant consumes `chat-events` (`CustomerMessageSent`, to decide
whether to reply) and `catalog-events` (`ProductUpdated`, to re-embed a
product into its own `product_embeddings` table). It produces no events
itself — replies are injected back into Chat via a synchronous internal
call (`POST /rooms/{id}/messages`), not published to Kafka, so there's no
`ai-assistant-events` topic. See
[services/ai-assistant/README.md](../services/ai-assistant/README.md).

`telemetry-aggregates` (STR-147) consumes `telemetry-events`' new
`TemperatureRecorded` — staged by Telemetry's `POST /measurements` handler
via its existing outbox (same instance/topic, no new topic) — to maintain
a CQRS read model of hourly temperature aggregates on its own Postgres
instance (`telemetry-aggregates-db`), independent of telemetry-db. This is
a hybrid update path: the Kafka consumer applies a running-average
incremental update per event, and a periodic backfill job
(`BACKFILL_INTERVAL_MINUTES`, default 15) recomputes and overwrites the
current + previous hour directly from telemetry-db's raw readings as the
correctness backstop. See
[services/telemetry-aggregates/README.md](../services/telemetry-aggregates/README.md)
for the full idempotency guarantee and why violation detection
deliberately does **not** read from this service.

## MCP Gateway (not a Kafka participant)

`mcp-gateway` produces and consumes no topics — it's included here because
it's the other piece of internal infrastructure sitting alongside the
broker, not because it uses it. It exposes Orders/Inventory/Catalog/
Telemetry/Security/Chat as MCP tools over HTTP (`GET /mcp/tools`,
`POST /mcp/tools/call`), each tool a thin `httpx` wrapper that calls the
relevant domain service synchronously with its own Gateway-minted internal
token — the same request/response model every other domain service already
uses, just fronted by one consistent tool registry instead of a client
class per consumer. AI Assistant is the first intended caller (see
`MCP_GATEWAY_URL` in its compose environment); a full agent runtime wired
through the ReAct loop is future scope. See
[services/mcp-gateway/README.md](../services/mcp-gateway/README.md).

## Verifying the broker is alive

```bash
docker compose up -d kafka kafka-topic-init
./scripts/test-kafka-smoke.sh
```

This only proves the broker/topics are reachable. Orders and Inventory have
real producers/consumers implementing the reservation saga (transactional
outbox on both sides, idempotent consumers) — see
[scripts/test-reservation-saga.sh](../scripts/test-reservation-saga.sh) for
an end-to-end run against the real broker. Chat is a producer-only client of
`chat-events` (transactional outbox, same pattern) — see
[scripts/test-chat-saga.sh](../scripts/test-chat-saga.sh).

## Known, accepted gaps (dev-only stage)

- **No Kafka auth/ACL.** `PLAINTEXT` listeners, no per-service credentials —
  same trust model as the rest of the compose stack. Same class of issue as
  the pre-existing internal-token note in
  [services/orders/README.md](../services/orders/README.md#internal-token-forwarding-to-inventory):
  acceptable for a solo-developer/learning-scale local stack, needs
  revisiting before any prod/AWS configuration.
- **`check-availability` doesn't account for `reserved_quantity`.** Once the
  reservation saga (Orders outbox → Inventory idempotent consumer) is
  reserving stock, `check-availability` (used by Orders' checkout pre-check)
  still sums each product's raw `quantity`, unaware of how much is already
  held by other in-flight orders' reservations. This is a UX gap, not a
  correctness bug — Inventory's actual reservation logic never oversells —
  but it means checkout can pass its optimistic pre-check and still land
  `Rejected` once the real reservation runs. Candidate follow-up: should
  `check-availability` subtract `reserved_quantity`?
- **Mailpit, not a real email provider.** Notifications sends via Mailpit, a
  local SMTP stub with a web UI/REST API — no real inbox is ever reached.
  Same accepted dev-only trade-off as the two gaps above: avoids real API
  keys/external dependency for local dev and CI, at the cost of needing a
  real provider (SES/Resend/etc.) wired in before any prod/AWS deploy. See
  [services/notifications/README.md](../services/notifications/README.md).
- **`telemetry-simulator` generates synthetic data, not a real DHT22
  sensor.** It's a small container that POSTs random-walk readings around a
  configurable base temperature to Telemetry's `/measurements` endpoint on
  the same 5-minute cadence a real device would use — good enough to
  exercise the violation-detection logic and `test-telemetry-saga.sh`, but
  it never talks to real hardware. Same class of gap as the two above:
  acceptable for local dev, needs a real ingestion path (MQTT/device
  gateway/etc.) before any prod deploy. Relatedly, violation detection
  itself runs on a 5-minute timer rather than true stream processing —
  acceptable at this measurement cadence, but it means a violation is
  detected up to one check-interval late, not the instant the underlying
  condition becomes true. See
  [services/telemetry/README.md](../services/telemetry/README.md).
- **AI Assistant requires real GCP Application Default Credentials, no
  local LLM fallback.** (STR-161b: was a real `OPENAI_API_KEY` before the
  Gemini migration.) `docker compose up` without them set starts the
  service fine, but every chat completion/embedding call fails until real
  ADC is provided — same class of external-dependency trade-off as the
  Mailpit gap above. Embeddings are also built lazily: `product_embeddings`
  stays empty until Catalog publishes a `ProductUpdated` event for each
  product, so a
  fresh stack has no RAG context until either an admin edits every product
  once or `scripts/seed-embeddings.sh` is run to trigger it directly. Rate
  limiting (`AI_RATE_LIMIT`, default 10/hour) is per-room, not per-customer —
  a customer with multiple open rooms gets the limit again in each one. See
  [services/ai-assistant/README.md](../services/ai-assistant/README.md).
