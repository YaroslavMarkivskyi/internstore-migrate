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
| `order-events` | `OrderCreated`, `PaymentConfirmed`, `OrderCancelled` | Orders service |
| `inventory-events` | `StockReserved`, `StockReservationFailed`, `StockDecremented`, `ReservationExpired` | Inventory service |
| `telemetry-events` | `TemperatureThresholdViolated`, `TemperatureNormalized` | Telemetry service |
| `chat-events` | `UnreadMessageReceived` | Chat service (future) |

All topics: 1 partition, replication factor 1 (single broker, no HA at this
stage). Created automatically by the `kafka-topic-init` compose service on
`docker compose up -d`.

## Verifying the broker is alive

```bash
docker compose up -d kafka kafka-topic-init
./scripts/test-kafka-smoke.sh
```

This only proves the broker/topics are reachable — no consumer business
logic exists yet for Telemetry/Chat. Orders and Inventory now have real
producers/consumers implementing the reservation saga (transactional
outbox on both sides, idempotent consumers) — see
[scripts/test-reservation-saga.sh](../scripts/test-reservation-saga.sh) for
an end-to-end run against the real broker.

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
