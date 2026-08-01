# ADR 0002: Event broker — Kafka (KRaft mode)

- Status: Accepted
- Date: 2026-08-01

## Context

The reservation saga for Orders/Inventory
(`OrderCreated → StockReserved/StockReservationFailed → PaymentConfirmed →
StockDecremented`, plus `ReservationExpired`) is designed as choreography
over an event bus, not orchestration. No broker exists yet in
docker-compose — it's a hard blocker for a real Orders service (Inventory
can start without it: read-only endpoints per STO-02/03 first, event
consumption comes later).

## Decision

Use **Kafka**, single node, **KRaft mode** (no Zookeeper).

### Options considered

| Option | Verdict | Why |
|---|---|---|
| Kafka | **Chosen** | Gives an event log with replay, which is a real fit for Inventory (full stock-movement history is a natural future event-sourcing candidate). Solo-developer operational cost is one broker to run and understand, reused for every event-driven interaction (Orders/Inventory saga, telemetry, chat), rather than splitting request-style and stream-style traffic across two different systems for no concrete benefit at this scale. |
| RabbitMQ | Rejected for now | Simpler mental model and lighter footprint, and would be perfectly adequate for the saga's choreography (no ordering/replay requirement there). Rejected specifically because it does *not* cover the Inventory replay/event-sourcing use case, and running RabbitMQ **and** Kafka later just to get that would mean two brokers to operate instead of one. Worth revisiting only if Kafka's operational overhead turns out not to be worth it for a project this size. |

KRaft over Zookeeper: fewer moving parts to run and reason about for a
single-node dev setup — no separate Zookeeper ensemble, one container, one
persistent volume.

## Topics

Fixed in advance, one topic per bounded-context event stream (not one topic
per event type — consumers filter/dispatch on an `eventType` field in the
message):

| Topic | Events | Producer (future) |
|---|---|---|
| `order-events` | `OrderCreated`, `PaymentConfirmed`, `OrderCancelled` | Orders service |
| `inventory-events` | `StockReserved`, `StockReservationFailed`, `StockDecremented`, `ReservationExpired` | Inventory service |
| `telemetry-events` | `TemperatureThresholdViolated`, `TemperatureNormalized` | Telemetry service |
| `chat-events` | `UnreadMessageReceived` | Chat service (future) |

All created with `--partitions 1 --replication-factor 1` — single broker,
no HA requirement at this stage. Revisit partition count if a topic needs
per-key ordering guarantees under concurrent producers.

## Local development

`docker compose up -d` starts:

- `kafka` — `apache/kafka` image, KRaft combined broker+controller mode,
  persistent volume (`kafka_data`), advertised listener on `localhost:29092`
  for host access and `kafka:9092` for other containers.
- `kafka-topic-init` — one-shot container, depends on `kafka` being
  healthy, creates the four topics above via `kafka-topics.sh` and exits.

Connection details and topic list are documented in
[docs/EVENT_BROKER.md](../EVENT_BROKER.md) for services that need to
produce/consume.

[scripts/test-kafka-smoke.sh](../../scripts/test-kafka-smoke.sh) publishes a
test message to `order-events` and confirms a consumer receives it —
confirms the broker is alive, nothing more.

## What this does NOT cover

Deliberately out of scope for this ADR/task:

- Consumer business logic — lands with Inventory/Orders/Telemetry/Chat as
  those services are built.
- Outbox pattern in producers — needed once a service (Orders) writes to
  its own DB and publishes an event in the same logical operation.
- Consumer idempotency — needed once real consumer code exists.

## Consequences

- One more stateful service to operate locally (Kafka + its volume).
- Every future domain service that produces/consumes events depends on the
  topic names and message shape documented in
  [docs/EVENT_BROKER.md](../EVENT_BROKER.md); renaming a topic or changing
  an event's shape is a breaking change across services once consumers
  exist.
- Single broker, single partition per topic: no HA and no ordering
  guarantees beyond a single partition. Acceptable for a learning-scale
  project; would need revisiting (more brokers, replication factor > 1,
  partition strategy) before any real production use.
