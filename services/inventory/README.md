# inventory

Stocks and stock items for InternStore. Second domain service split out of
the monolith — chosen because it's the producer of `StockReserved` /
`StockReservationFailed` events Orders will consume in the checkout saga, and
the owner of the one synchronous endpoint in the system
(`POST /stocks/check-availability`, called by Orders at checkout). Getting
Inventory's read/write surface in place now means Orders can build against it
once it exists.

Same stack as [services/catalog](../catalog): Python/FastAPI/SQLAlchemy
(async)/Alembic, its own Postgres database with zero shared tables, and the
same internal-token verification pattern (see [src/inventory/auth.py](src/inventory/auth.py),
which mirrors `services/catalog/src/catalog/auth.py`).

## Data model

- `Stock` — a warehouse/store. `temperature` is nullable/pending — still not
  populated here; Telemetry keeps its own timeseries keyed by this same
  `Stock.id` rather than writing back into this column (see
  [services/telemetry](../telemetry)). Plain directly-mutated table — **not**
  event-sourced (see below): STR-149 event-sources the `(stock_id,
  product_id)` quantity/reservation aggregate, not warehouse metadata.
- `StockItem` — quantity of a product at a given stock. `product_id` is a
  bare UUID referencing Catalog's `Product.id`; there is no foreign key to
  Catalog's database, and this service never validates the product exists.
  `is_unavailable` is set by the `telemetry-events` consumer on
  `TemperatureThresholdViolated`, and cleared by an admin via
  `POST /stocks/{id}/items/{itemId}/mark-available` (STR-149 — previously
  nothing ever cleared this flag; see below).
  **As of STR-149, this table is a read-model *projection*, not a source of
  truth** — see "Event sourcing" below before touching any code that writes
  to it.

## Event sourcing (STR-149)

Inventory used to store state directly in `stock_items`, publishing domain
events as a side effect via the transactional outbox — event-*driven*, not
event-*sourced*: the events were a consequence of state changes, not the
source of truth. STR-149 replaced this with a genuine full replacement, not
an additive layer: **`stock_events` is now the sole source of truth** for the
`(stock_id, product_id)` aggregate (append-only, never updated or deleted);
`stock_items` keeps its pre-STR-149 shape as a **projection**, folded from
`stock_events` — every downstream reader (Orders' `check-availability`,
`services/mcp-gateway`'s tools, admin endpoints) sees the exact same read
contract as before.

**Event types** (see [src/inventory/events.py](src/inventory/events.py) for
the exhaustive, authoritative list and [src/inventory/projector.py](src/inventory/projector.py)'s
`apply_event` for what each one means): `StockItemCreated`, `ItemReceived`,
`ItemMovedOut`/`ItemMovedIn`, `StockReserved`, `StockReleased`,
`StockConsumed`, `StockItemQuantitySet`, `StockItemRemoved`,
`MarkedUnavailable`, `MarkedAvailable`. This list was reconciled against the
service's actual endpoints/consumers, not assumed from the ticket, with a
few documented discrepancies from STR-149's original write-up:

- `ItemMoved` doesn't exist as a single event type. A move mutates *two*
  aggregates (`stock_id` and `to_stock_id`), and a `stock_events` row belongs
  to exactly one aggregate's stream — so a move appends `ItemMovedOut` to the
  source aggregate and `ItemMovedIn` to the destination aggregate, both in
  one DB transaction, correlated by a shared `move_id` in their payloads
  purely for audit purposes.
- `StockItemQuantitySet` (the admin absolute-quantity-correction endpoint)
  and `StockItemRemoved` (item deletion) aren't in the ticket's original
  event list, but both are real state-changing endpoints with no other event
  to represent them — added to keep the audit trail complete.
- `MarkedAvailable` had no trigger anywhere in the pre-STR-149 codebase
  (`is_unavailable` was strictly one-way). A new admin endpoint,
  `POST /stocks/{id}/items/{itemId}/mark-available`, was added specifically
  to give this event a producer — flagged as new user-facing capability, not
  a pure refactor.
- `create_stock`/`update_stock`/`delete_stock` (the `Stock` warehouse entity)
  are **not** event-sourced — out of scope; see the Data model section above.
- The ticket's reservation-saga framing ("both sagas call Inventory's REST
  endpoints synchronously") is only true for the Temporal-orchestrated saga
  (`services/checkout-workflow`'s `reserve_stock`/`release_stock` activities,
  calling `POST /stocks/reserve`/`POST /stocks/release`). The Kafka
  choreography saga's reserve/release happen as **in-process function calls**
  from `consumers/order_events.py` into `commands.build_reserve`/
  `build_consume` — never over HTTP.

**Aggregate identity**: `aggregate_id = uuid.uuid5(AGGREGATE_NAMESPACE,
f"{stock_id}:{product_id}")` (see
[src/inventory/events.py](src/inventory/events.py)`.compute_aggregate_id`).
Deterministic and namespace-fixed, so any caller (a router, the projector,
the data-backfill migration) can compute the same stream identity
independently, with no lookup/registry table — this is what lets
`stock_events.aggregate_id` be a single `UUID` column rather than a composite
key. This is a narrow, deliberate deviation from the rest of this repo's
plain `uuid.uuid4()` convention, used only here. `stock_items` also carries a
`UNIQUE(stock_id, product_id)` constraint as defense-in-depth (not
load-bearing — the projector is the sole writer, already serialized by
`stock_events`' own concurrency mechanism below — but cheap insurance against
a projector bug producing two rows for one aggregate).

**Concurrency control**: `stock_events`' `UNIQUE(aggregate_id,
sequence_number)` constraint is the *sole* concurrency-control mechanism for
this aggregate — it replaces the row-level locking a directly-mutated
`stock_items` `UPDATE` would otherwise need. Appending requires knowing an
aggregate's current last `sequence_number` and inserting at `+1`; a
constraint violation means a concurrent writer already claimed that slot, and
the whole command is retried against freshly-read state (see
[src/inventory/commands.py](src/inventory/commands.py)`.run_with_retry`, and
`event_store.append_events`/`ConcurrencyConflict`). **This is the load-bearing
correctness mechanism that keeps two concurrent reservations for the same
product from both succeeding** — the exact thing that used to depend on
`stock_items.reserved_quantity`'s row-level UPDATE semantics.

**Synchronous projection — read this before changing anything here.** Every
write path is: validate the command → append the resulting event(s) for
every aggregate touched → fold them into the `stock_items` projection —
**all inside the same DB transaction**, committed once
(`commands.run_with_retry`/`commands.apply`, `projector.project_and_upsert`).
A caller's very next read sees consistent state immediately; there is no
eventually-consistent window between "the event exists" and "the projection
reflects it".

**This is a deliberate deviation from `services/telemetry-aggregates`' CQRS
pattern** (STR-147) — that service's read model is built by an *async* Kafka
consumer plus a periodic backfill correctness-backstop, which is correct for
a reporting read model that can tolerate seconds of staleness. It is **not**
acceptable for Inventory's projection, which gates real-time reservation
decisions used by two live sagas (see below) — a naive async-projection
migration here would silently break both sagas' read-after-write consistency
guarantees. **Do not "consistency" this into an async design by analogy with
Telemetry-aggregates.** If you're tempted to, re-read this paragraph first.

**Snapshots** (`stock_snapshots`, [src/inventory/snapshots.py](src/inventory/snapshots.py),
background worker in [src/inventory/snapshot_worker.py](src/inventory/snapshot_worker.py)):
periodic, purely to bound replay cost. **Not needed for the live
projection's correctness or freshness** — that's always current by
construction, per the synchronous-projection point above. Snapshots exist
only to bound (a) disaster-recovery rebuild time of `stock_items` from
`stock_events`, and (b) replay cost for the `as-of` point-in-time endpoint on
aggregates with a long history. Defaults: a snapshot is taken once an
aggregate has accumulated 100 events since its last snapshot, or its last
snapshot is more than an hour old, whichever comes first — 100 bounds
worst-case replay for a hot SKU; the 1-hour ceiling covers low-traffic
aggregates that might otherwise never cross the count threshold. Pure
operational tuning (`SNAPSHOT_EVENT_THRESHOLD`/`SNAPSHOT_MAX_AGE` in
`snapshots.py`), cheap to revise, no schema/contract implications.

**Two distinct event concepts, do not conflate**: `stock_events` (this
section — the event-sourcing source of truth, new in STR-149) and
`outbox_events` (the pre-existing, unrelated inter-service Kafka pub/sub
outbox — `StockReserved`/`ItemAdded`/etc. notifications to Orders/Telemetry,
see the Kafka section below) are two separate tables serving two separate
purposes, both still present after STR-149.

**Migration** (two revisions:
[99d45f76e7ae_event_sourcing_schema.py](migrations/versions/99d45f76e7ae_event_sourcing_schema.py) and
[85cc420998d1_backfill_stock_events.py](migrations/versions/85cc420998d1_backfill_stock_events.py)):
a schema migration (pure DDL — `stock_events`, `stock_snapshots`, the
`stock_items` unique constraint) followed by a one-time Python data-backfill
migration converting every existing `stock_items` row into a
`StockItemCreated` event (current `quantity` as `initial_quantity`), plus a
synthetic `StockReserved` event per currently-outstanding (`status=
'reserved'`) reservation — read from Inventory's **own**
`reservations`/`reservation_items` tables. This corrects the ticket's
original instruction to cross-reference Orders' Pending orders: Inventory's
own `Reservation` rows are already the authoritative record of what
Inventory itself considers outstanding at cutover time, and the migration
has no business reading another service's database (also out of scope per
"no change to Orders' read contracts"). `stock_items` itself is left
untouched by this migration — it already holds the correct projection; the
migration only backfills the event log underneath it, so the projector finds
and updates the same rows (same ids) afterward rather than re-creating them.
The row-to-event transform lives in
[src/inventory/migration_support.py](src/inventory/migration_support.py)
(`build_backfill_events`) as a plain, `alembic.op`-free function specifically
so it can be unit-tested directly (see `tests/test_migration.py`) without
needing real Alembic machinery.

**Rollout**: big-bang cutover, no shadow-mode/feature-flag — schema migration
→ data migration → code cutover (all direct-mutation code paths removed,
not flag-gated alongside the new path) → deploy, gated on the full test
suite plus `scripts/test-reservation-saga.sh`,
`scripts/test-temporal-saga.sh`, and `scripts/test-event-sourcing.sh` all
passing unchanged. Chosen over shadow-mode because the synchronous
same-transaction projection already eliminates the main risk shadow-mode
exists to catch (eventual-consistency drift between an old and new
representation), and no feature-flag pattern exists anywhere in this repo to
build shadow-mode on top of.

**New endpoints** (admin-only, read-only, additive — the audit-trail and
time-travel payoff):

- `GET /stocks/{stockId}/{productId}/history?cursor=&limit=` — paginated
  (keyset on `sequence_number`, default `limit=50`, max `200`) raw event
  history for one aggregate.
- `GET /stocks/{stockId}/{productId}/as-of?timestamp=` — point-in-time
  reconstruction: nearest snapshot at or before `timestamp`, replayed forward
  through events up to `timestamp`. 404 if the aggregate didn't exist yet (no
  events at or before that time).

Both reuse `projector.apply_event`/`replay` — the exact same fold function
the live projection is built from — so history/as-of are never a second
implementation of what an event means.

## Endpoints

- `GET /health` — liveness check.
- `POST /stocks` — admin-only. Body: `{"name": "..."}` (2-100 chars,
  unique), `temperature` optional. 409 on duplicate name.
- `GET /stocks` — public, list stocks with `temperature` (`null` until
  Telemetry integration lands).
- `GET /stocks/{id}/items` — public, list stock items for one stock. 404 if
  the stock doesn't exist. (STO-02)
- `GET /items` — public, consolidated quantity per product across all
  stocks. Optional filters: `stock_id`, `min_quantity`, `max_quantity`.
  Filtering by Catalog attributes like category/price is explicitly out of
  scope here — Inventory doesn't own that data; composing it belongs to a
  future Gateway/BFF ticket. (STO-02)
- `POST /stocks/{id}/items` — admin-only. Body: `{"product_id", "quantity"}`
  (`quantity` > 0). Increments existing quantity for that product at that
  stock, or creates a new row. 404 on unknown stock. (STO-01)
- `POST /stocks/{id}/items/{itemId}/move` — admin-only. Body:
  `{"to_stock_id", "quantity"}`. Moves quantity from `itemId` (must belong to
  `{id}`) to the destination stock, upserting there. 404 if the stock or item
  doesn't exist, 422 on insufficient quantity or same-stock move. (STO-03)
- `POST /stocks/{id}/items/{itemId}/mark-available` — admin-only (STR-149).
  Clears `is_unavailable`. The admin-facing counterpart to the
  `telemetry-events` consumer's automatic `MarkedUnavailable` — see "Event
  sourcing" above for why this is new rather than a pre-existing path.
- `POST /stocks/check-availability` — the sync contract Orders calls at
  checkout. Requires a valid `X-Internal-Token` (any role — customer, admin,
  or guest — since any of them can check out; see
  [services/orders](../orders)), forwarded by Orders from the caller's own
  token rather than a synthetic Orders-service identity. Body:
  `{"items": [{"product_id", "quantity"}, ...]}`. Returns per-product
  `available` (summed across all stocks) and `sufficient`, plus a top-level
  `sufficient` that's true only if every line item is. Documented in
  [libs/contracts/inventory/check-availability.md](../../libs/contracts/inventory/check-availability.md).
- `POST /stocks/reserve` / `POST /stocks/release` — STR-139: the second and
  third synchronous endpoints in the system, added for
  `services/checkout-workflow`'s Temporal activities (`reserve_stock` /
  `release_stock`) to call directly instead of going through the
  choreographed `order-events` → `try_reserve` path. Both are idempotent by
  `order_id` (Reservation.order_id's existing unique constraint) — a
  retried/redelivered call is a no-op returning the current state, which is
  what makes `release_stock`'s unbounded compensation retries in
  `CheckoutWorkflow` safe. Neither publishes an outbox/Kafka event: the
  Temporal-orchestrated checkout is deliberately choreography-free for the
  steps it awaits directly, so there's no consumer that should react to
  these calls the way `handle_order_created` reacts to `OrderCreated`.
  `POST /stocks/reserve` — `{order_id, items: [{product_id, quantity}]}` →
  `{order_id, status: "reserved" | "insufficient_stock"}`.
  `POST /stocks/release` — `{order_id}` → `{order_id, status: "released" | "not_found"}`.
  **STR-149: these two contracts are frozen** — internal implementation now
  appends `stock_events` + updates the projection synchronously (with
  retry-on-conflict) instead of a direct `UPDATE`, but request/response
  shapes are byte-for-byte unchanged. See "Event sourcing" above.

Not in scope for this ticket (see the task write-up): the STO-01
fingerprint/NFC part of EP-08/09.

## Kafka

- Producer (outbox): `ItemAdded` on `inventory-events`, staged on the same
  commit as `POST /stocks/{id}/items` and the destination side of
  `POST /stocks/{id}/items/{itemId}/move` — Telemetry consumes this to build
  its `{store_id, product_id}` threshold cache. This outbox (`outbox_events`)
  is unrelated to `stock_events` (STR-149's event-sourcing log) — see "Event
  sourcing" above.
- Consumer: `order-events` → `OrderCreated`/`PaymentConfirmed` (the Kafka
  choreography saga). As of STR-149, calls `commands.build_reserve`/
  `build_consume` directly against the consumer's own session (no retry
  loop — ADR 0002's single-partition topics mean there's no concurrent
  writer to race here) rather than mutating `StockItem` in place; still
  publishes `StockReserved`/`StockReservationFailed`/`StockDecremented` on
  `inventory-events` exactly as before (see
  [src/inventory/consumers/order_events.py](src/inventory/consumers/order_events.py)).
- Consumer: `telemetry-events` → `TemperatureThresholdViolated` sets the
  matching aggregate's `is_unavailable = true` (as of STR-149, via
  `MarkedUnavailable` + the synchronous projection, not a direct column
  write). Idempotent via the existing `processed_events` ledger; a
  redelivery after an admin manually cleared the flag via
  `mark-available` is a no-op (see
  [src/inventory/consumers/telemetry_events.py](src/inventory/consumers/telemetry_events.py)).

## Auth

Every write endpoint validates the `X-Internal-Token` header locally — HMAC
(HS256) signature, `iss`, `exp` — against the same shared secret
`auth-backend` mints with (`INTERNAL_TOKEN_SECRET`). This service never
trusts `X-User-Id`/`X-User-Role` headers directly and never calls back to
Keycloak or auth-backend.

## Local dev without Docker

```bash
cd services/inventory
cp .env.example .env   # point DATABASE_URL at a local Postgres
uv sync
uv run alembic upgrade head
uv run uvicorn inventory.main:create_app --factory --reload
```

Run tests (self-contained, in-memory SQLite, no DB needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d inventory-db inventory
```

Reachable through nginx at `/api/inventory/*` (see
[nginx/nginx.conf](../../nginx/nginx.conf)), not exposed on the host
directly — same pattern as catalog.

End-to-end smoke test against the real gateway with real Keycloak-issued
tokens (401/403/201/200 through nginx, quantity accumulation, move, and all
three check-availability outcomes):

```bash
docker compose up -d --build inventory-db inventory nginx
./scripts/verify-inventory-gateway.sh
```

STR-149's event-sourcing verification (event history, as-of reconstruction,
and that both existing reservation sagas still behave identically against
the event-sourced implementation) — run all three together as the merge
gate for any change to `commands.py`/`projector.py`/`event_store.py`:

```bash
docker compose up -d --build \
  temporal temporal-db temporal-ui payments payments-db \
  checkout-workflow-worker orders inventory nginx keycloak kafka kafka-topic-init
./scripts/test-reservation-saga.sh
./scripts/test-temporal-saga.sh
./scripts/test-event-sourcing.sh
```

## Migrations

New migration after changing `src/inventory/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://inventory:inventory@localhost:5434/inventory \
  uv run alembic revision --autogenerate -m "describe the change"
```
