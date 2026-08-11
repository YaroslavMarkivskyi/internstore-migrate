# telemetry

Temperature monitoring for InternStore. Fifth domain service — a hybrid
event producer/consumer: it receives temperature measurements from a
dev-only simulator container, stores a timeseries per store, detects
sustained threshold violations, and publishes `TemperatureThresholdViolated`
on `telemetry-events` when one is confirmed.

Same stack as [services/inventory](../inventory):
Python/FastAPI/SQLAlchemy(async)/Alembic, its own Postgres database with
zero shared tables, and the same internal-token verification pattern (see
[src/telemetry/auth.py](src/telemetry/auth.py)).

## Data model

- `Store` — a warehouse/store. `id` is always assigned explicitly to match
  Inventory's `Stock.id`; there's no separate "store created" event to
  sync from, so a row is lazily upserted the first time Telemetry sees a
  given id, via `POST /measurements` or an inventory-events message (see
  [src/telemetry/stores.py](src/telemetry/stores.py)). `threshold_temp` is
  a per-store override, configurable by admin via `PATCH /stores/{id}`.
- `TemperatureReading` — one timeseries row per measurement.
- `Incident` — created when a sustained violation is confirmed
  (`product_id` references Catalog's `Product.id`, bare UUID, no FK — same
  cross-service convention as Inventory's `StockItem.product_id`).
- `StoreProductThreshold` — local cache of each `{store_id, product_id}`
  pair's `max_temp`, built entirely from `catalog-events`
  (`ProductThresholdUpdated`) and `inventory-events` (`ItemAdded`) — never
  the source of truth, always rebuildable from those event streams.

## Violation detection

A background task (`run_violation_checker`, interval configurable via
`VIOLATION_CHECK_INTERVAL_SECONDS`, default 300s to match the simulator's
cadence) re-evaluates every `{store, product}` pair with a known
`max_temp` every cycle. This is a **sustained** condition, not an average:
every reading within the trailing window (`VIOLATION_WINDOW_SECONDS`,
default 3600s / 1h) must exceed `max_temp + 1°` — a spike that dips back
down mid-window is not a violation even if the mean is high (see
[src/telemetry/violations.py](src/telemetry/violations.py)). A violation
creates an `Incident` row and stages `TemperatureThresholdViolated` on the
outbox in the same transaction — the outbox worker publishes it to
`telemetry-events`, matching the payload shape Notifications' existing
handler stub expects (`stock_id`, `product_id`, `temperature`,
`deviation`). Duplicate incidents for the same still-violating pair are
suppressed while an `Incident` from within the current window already
exists.

Known, accepted dev-only gaps (see
[docs/EVENT_BROKER.md](../../docs/EVENT_BROKER.md)): the timer-based check
isn't true stream processing, and `telemetry-simulator` generates
synthetic data rather than reading a real DHT22 sensor.

## Kafka

- Consumers:
  - `catalog-events` → `ProductThresholdUpdated` — updates `max_temp` for
    every existing `store_product_thresholds` row for that product. Does
    not create new rows; a store only starts tracking a product once
    Inventory says so via `ItemAdded`.
  - `inventory-events` → `ItemAdded` — lazily creates the `Store` row (if
    new) and a `store_product_thresholds` row for that
    `{store_id, product_id}` pair (`max_temp` stays whatever's cached,
    `null` if this is a new pair).
- Producer (outbox):
  - `TemperatureThresholdViolated` on `telemetry-events`.
  - `TemperatureRecorded` on `telemetry-events` (STR-147) — staged after
    every `POST /measurements` insert, one event per `{store_id,
    product_id}` pair the store currently tracks (`POST /measurements`
    itself only carries `{store_id, temperature, humidity}`; product
    association is looked up from `store_product_thresholds`, same as
    `violations.py`'s own per-`{store, product}` loop). A store with no
    tracked products yet stages nothing. Payload:
    `{store_id, product_id, temperature, humidity, recorded_at}`. Consumed
    by `services/telemetry-aggregates` to maintain hourly aggregates for
    chart/reporting queries — see
    [services/telemetry-aggregates/README.md](../telemetry-aggregates/README.md).
    This service's own tables and endpoints are unchanged by that
    consumer.

Both consumers dedup via a `processed_events` ledger, same pattern as
Inventory/Orders.

## Endpoints

- `GET /health` — liveness check.
- `POST /measurements` — no auth dependency; called directly by
  `telemetry-simulator` on the compose network, not through the Gateway.
  Body: `{"store_id", "temperature", "humidity"?}`. Lazily creates the
  store if unknown.
- `GET /stores` — public, list stores with `current_temperature` (latest
  reading) and `has_open_violation` (any incident in the last hour).
- `PATCH /stores/{id}` — admin-only. Body: `{"name"?, "threshold_temp"?}`.
- `GET /stores/{id}/readings?period=week|month|3months|all` — admin-only,
  timeseries for charting. 404 if the store doesn't exist.
- `DELETE /stores/{id}/readings` — admin-only, deletes all historical
  readings for a store.
- `GET /stores/{id}/incidents` — admin-only, list incidents for a store.
- `DELETE /stores/{id}/incidents/last` — admin-only, deletes only the most
  recent incident.
- `DELETE /stores/{id}/incidents` — admin-only, deletes all incidents.

## Auth

Every admin endpoint validates the `X-Internal-Token` header locally — same
HMAC (HS256) verification as every other domain service (see
[src/telemetry/auth.py](src/telemetry/auth.py)). `POST /measurements` is
the one exception — it's the simulator's ingestion path, not an
admin-facing endpoint.

## Local dev without Docker

```bash
cd services/telemetry
cp .env.example .env   # point DATABASE_URL at a local Postgres
uv sync
uv run alembic upgrade head
uv run uvicorn telemetry.main:create_app --factory --reload
```

Run tests (self-contained, in-memory SQLite, no DB needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d telemetry-db telemetry telemetry-simulator
```

Reachable through nginx at `/api/telemetry/*` (see
[nginx/nginx.conf](../../nginx/nginx.conf)) for the admin-facing endpoints;
`telemetry-simulator` talks to `POST /measurements` directly over the
compose network, bypassing the Gateway — same as Orders' direct call to
Inventory's `check-availability`.

End-to-end saga verification against the real gateway, real Kafka broker,
and Mailpit (via `scripts/test-telemetry-saga.sh`):

```bash
docker compose up -d --build
./scripts/test-telemetry-saga.sh
```

## Migrations

New migration after changing `src/telemetry/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://telemetry:telemetry@localhost:5436/telemetry \
  uv run alembic revision --autogenerate -m "describe the change"
```
