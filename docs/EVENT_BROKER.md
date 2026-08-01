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
logic exists yet. That lands with each domain service (Inventory, Orders,
Telemetry, Chat) as it's built.
