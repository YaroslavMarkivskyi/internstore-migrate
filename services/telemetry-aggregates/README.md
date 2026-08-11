# telemetry-aggregates

CQRS read model for Telemetry (STR-147). Owns hourly temperature
aggregates for chart/reporting queries, kept up to date via a **hybrid**
pipeline: a Kafka consumer for low-latency incremental updates, plus a
periodic backfill job for correctness. Same stack as every other domain
service: Python/FastAPI/SQLAlchemy(async)/Alembic.

## Why this exists

[services/telemetry](../telemetry) currently answers every read
(`GET /stores/{id}/readings?period=...`) by scanning its full
`temperature_readings` timeseries table, filtered by date range. That
competes with the same table's high-frequency small writes
(`POST /measurements` every 5 minutes per store) and with
violation-detection's own hourly-window query. This service splits reads
that only need hourly resolution off onto their own storage and their own
update path, so telemetry-db is free to stay a lean write/short-window-read
store.

## Physical instance separation, not a schema split

`telemetry-aggregates-db` is a genuinely separate Postgres instance (own
`DATABASE_URL`), not a second schema inside telemetry-db and not a
materialized view. This is a deliberate demonstration of CQRS with real
storage isolation — see docker-compose.yml / k8s/base for the second
StatefulSet. The one place this service reads telemetry-db at all is
`backfill.py`, documented below as the explicit, scoped exception.

## Data model

```
hourly_aggregates (
    store_id UUID,
    product_id UUID,
    hour_bucket TIMESTAMP,  -- truncated to the hour, e.g. 2026-08-11 14:00:00
    avg_temperature NUMERIC,
    min_temperature NUMERIC,
    max_temperature NUMERIC,
    reading_count INT,
    updated_at TIMESTAMP,
    PRIMARY KEY (store_id, product_id, hour_bucket)
)
```

`processed_events` is the incremental consumer's dedup ledger, same
pattern as telemetry's own.

## Idempotency guarantee

The composite primary key `(store_id, product_id, hour_bucket)` is the
whole mechanism that makes writing from two independent paths safe: both
the incremental consumer's upsert and the backfill job's
recompute-and-overwrite always target the *same row* for a given hour —
there's no way for the two paths to create divergent rows for the same
key. Concretely:

- **The incremental consumer** (`consumers/telemetry_events.py`) merges a
  new reading into whatever's currently in the row (running average —
  see below). A `processed_events` ledger keyed by Kafka `event_id` makes
  redelivery of the *same* message a no-op (see `test_idempotency.py`'s
  `test_redelivery_of_the_same_event_is_a_noop`-style coverage in
  `test_incremental_update.py`).
- **The backfill job** (`backfill.py`) never merges — every cycle it
  **overwrites** the row with avg/min/max/count computed fresh from
  telemetry-db's raw `temperature_readings` for that exact hour. Because
  this is a pure function of raw data (not of whatever was in the row
  before), running it any number of times, in any order, relative to the
  incremental path always converges to the same ground-truth value. This
  is what `test_idempotency.py` actually proves: whether the row already
  reflects a correct partial update, a stale value, or an arbitrarily
  wrong one, the next backfill overwrite lands on the same true numbers.

**What this guarantee does *not* claim**: it is not instant, real-time
consistency between the two paths for the same underlying reading. If the
consumer is down when a reading arrives, backfill will (correctly) include
that reading in its next overwrite from raw data. If the consumer then
restarts and — because Kafka only advances its committed offset past
messages it successfully dispatched — redelivers that same event, the
incremental merge will add it on top of a row that already accounts for
it, transiently over-counting. This drift is real but **bounded to one
backfill interval** (`BACKFILL_INTERVAL_MINUTES`, default 15): the next
backfill cycle overwrites it back to truth regardless. This is the
explicit trade-off of "hybrid, not backfill-only" — a backfill-only design
would have correctness but only ever be as fresh as the last cycle;
"hybrid" buys near-real-time freshness from the incremental path while
capping its worst-case error at one interval, self-healed automatically.
A future engineer should not read the PK/last-write-wins guarantee as "the
two paths can never disagree even for a moment" — they can, briefly; the
system's correctness claim is that they can never disagree *for more than
one backfill interval*.

## Incremental update path (Kafka consumer)

`consumers/telemetry_events.py` subscribes to `telemetry-events` and
handles `TemperatureRecorded`. It updates the aggregate using **only the
event payload** — no read-back to telemetry-db:

```
new_avg   = (old_avg * old_count + new_temp) / (old_count + 1)
new_min   = min(old_min, new_temp)
new_max   = max(old_max, new_temp)
new_count = old_count + 1
```

**This was a deliberate choice over a cross-database join.** The ticket's
alternative — on each event, re-query telemetry-db's raw readings for the
current hour and recompute — would work, but it reintroduces a
per-request cross-database dependency into the one code path this service
most wants to be cheap and decoupled (a high-frequency incremental
update). A running-average update needs nothing but the event's own
`temperature` and the row's current state, which keeps the read model
genuinely independent of telemetry-db on the hot path. The one place this
service legitimately needs telemetry-db at all is backfill, below — and
that's a periodic batch job, not a per-event join, so the cost profile is
completely different.

`hour_bucket` is computed by truncating the event's `recorded_at` to the
hour (`aggregation.truncate_to_hour`); a reading in a new hour always
creates a new row rather than merging into the previous one, since
`hour_bucket` is part of the primary key.

## Backfill job (periodic correctness backstop)

`backfill.py` runs every `BACKFILL_INTERVAL_MINUTES` (default 15) and, for
the **current and previous hour** (the previous hour catches
late-arriving events right at an hour boundary), queries telemetry-db's
raw `temperature_readings` for that window and **overwrites** the
corresponding `hourly_aggregates` row with the true avg/min/max/count. If
the incremental path missed events (consumer downtime, redelivery gaps) or
never ran at all for that window, this job is what makes the aggregate
correct — see "Idempotency guarantee" above.

**This is the one place this service reads telemetry-db** — the deliberate
exception to the "no cross-database dependency" preference stated above.
Its connection (`TELEMETRY_DB_URL`) connects as `telemetry_readonly`, a
dedicated Postgres role telemetry provisions in its own migration
(`services/telemetry/migrations/versions/69ff8539f688_...py`), GRANTed
`SELECT` only on the two tables this job reads
(`temperature_readings`, `store_product_thresholds`) — not the full-access
`telemetry` user. This was a real gap caught by STR-148's live
verification: the connection had been documented as "read-only in intent"
since this service's own STR-147 delivery, but nothing had actually
provisioned a role that enforces it — `docker-compose.yml`'s
`TELEMETRY_DB_URL` connected as the full read-write `telemetry` user until
that ticket's fix.

Telemetry's raw readings carry only `store_id` — `POST /measurements`
takes `{store_id, temperature, humidity}`, with product association
happening separately via `store_product_thresholds` (see
[services/telemetry/README.md](../telemetry/README.md)). So a store's raw
readings apply to every product it currently tracks; `backfill.py` fans
out its recompute across `store_product_thresholds` the same way
telemetry's own `POST /measurements` handler fans out one
`TemperatureRecorded` event per tracked product for a single physical
reading (see that service's README).

## Violation detection is explicitly out of scope for this service

Telemetry's violation detection (`services/telemetry/src/telemetry/violations.py`)
reads the last hour of **raw** readings, because it's a **sustained**
condition — every individual reading in the window must exceed the
threshold, not the average. Wiring violation detection to
`hourly_aggregates` would silently reintroduce the exact avg-vs-sustained
bug that was deliberately fixed there: an hourly average can be under
threshold even if every reading spiked above it late in the hour, or over
threshold from one early spike that then normalized — neither is a real
sustained violation. **Do not** redirect violation detection to this
service's data. This service exists for chart/reporting queries only.

## API

- `GET /aggregates/{store_id}/{product_id}?period=week|month|3months|all`
  — hourly aggregates for a store/product pair, ordered by `hour_bucket`.
  This is a **net-new, directly-consumed endpoint** — telemetry's existing
  `GET /stores/{id}/readings` is left untouched and does not proxy here
  (see [services/telemetry/README.md](../telemetry/README.md) — that
  endpoint's raw-table scan is unaffected by this ticket). Any future
  caller (frontend chart rendering, etc.) talks to this service directly.
- `GET /health` — liveness check.

Both endpoints validate `X-Internal-Token` locally (see `auth.py`, same
HMAC pattern as every other domain service); `GET /aggregates/...` is
admin-only, matching telemetry's own `GET /stores/{id}/readings`.

## Local dev without Docker

```bash
cd services/telemetry-aggregates
cp .env.example .env   # point DATABASE_URL and TELEMETRY_DB_URL at local Postgres instances,
                        # and set INTERNAL_TOKEN_SECRET to match auth-backend's
uv sync
uv run alembic upgrade head
uv run uvicorn telemetry_aggregates.main:create_app --factory --reload
```

Run tests (self-contained, in-memory SQLite for both this service's own DB
and the telemetry-db stand-in, no real Postgres needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d --build telemetry-aggregates-db telemetry-aggregates
./scripts/test-telemetry-aggregates.sh
```

## Migrations

New migration after changing `src/telemetry_aggregates/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://telemetry-aggregates:telemetry-aggregates@localhost:5437/telemetry-aggregates \
  uv run alembic revision --autogenerate -m "describe the change"
```

`src/telemetry_aggregates/telemetry_read_models.py` (the Core tables
`backfill.py` reads from telemetry-db) is deliberately excluded from
`Base.metadata` / this service's own migrations — it mirrors a schema this
service doesn't own and must never try to migrate.
