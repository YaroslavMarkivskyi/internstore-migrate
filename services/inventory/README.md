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
Firebase or auth-backend.

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

End-to-end smoke test against the real gateway with real Firebase-issued
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
  checkout-workflow-worker orders inventory nginx kafka kafka-topic-init
./scripts/test-reservation-saga.sh
./scripts/test-temporal-saga.sh
./scripts/test-event-sourcing.sh
```

## STR-150: live verification against real Postgres + both sagas

STR-149 above was unit-tested against SQLite (`Base.metadata.create_all`,
never Alembic) and its migration scripts were syntax-checked but never
executed. STR-150 ran the actual migration against real Postgres with
realistic seed data (multiple stores/products plus an in-flight,
`status='reserved'` reservation — the trickiest backfill case), then ran
both sagas and the new event-sourcing script repeatedly against the
migrated, event-sourced stack. Same standard as prior live-verification
tickets (#157, #160): no design changes, fix real bugs found while running
it, document them here.

**Migration dry-run**: `alembic upgrade head` against real Postgres with 9
pre-existing `stock_items` rows plus 6 seeded ones (including the in-flight
reservation: quantity=12, reserved_quantity=5) produced 16 `stock_events`
rows (15 `StockItemCreated` + 1 `StockReserved`). Replaying every
aggregate's events with `projector.replay` and comparing against the live
`stock_items` rows matched exactly, including the in-flight reservation's
reconstructed `quantity=12, reserved_quantity=5`. `stock_items` itself was
byte-for-byte unchanged by the migration, as designed. Re-running `alembic
upgrade head` against an already-migrated database is a clean no-op.

**Real bug found — migration fails on real Postgres, never caught by
SQLite tests**: `85cc420998d1_backfill_stock_events.py`'s `reservations_
table.c.status` was declared `sa.String()`, but on real Postgres `status`
is the native `reservation_status` enum (see `models.Reservation`); Postgres
has no implicit `VARCHAR = reservation_status` comparison operator, so the
migration's `WHERE status = 'reserved'` filter raised `UndefinedFunctionError:
operator does not exist: reservation_status = character varying` the first
time it ran against Postgres. SQLite has no native enum type, so
`test_migration.py` — which only ever exercises `migration_support.
build_backfill_events`, never this Alembic script — could never have caught
it. This is the exact category of gap the ticket flagged going in. Fixed by
declaring the column with the same `sa.Enum(...)` the model uses.

**Real bugs found while running the two sagas and the new event-sourcing
script** — all in the test scripts themselves, not in event-sourcing code,
but each one blocked the ticket's own Definition of Done until fixed:

- `scripts/test-reservation-saga.sh`'s expiry poll assumed a stale
  `RESERVATION_TTL_SECONDS=30` with a 60s timeout; both `docker-compose.yml`
  and `k8s/base/inventory/configmap.yaml` have actually set it to 300s for a
  while. `scripts/k8s/test-reservation-saga.sh` (STR-145) already found and
  fixed this — plus a second, compounding bug it surfaced (the reused
  `CUSTOMER_TOKEN` expiring mid-poll, since the external token's own
  lifespan is also 300s) — but neither fix was ever ported back to the
  compose original. Ported here.
- Both `test-reservation-saga.sh` and `test-event-sourcing.sh`'s
  `poll_until` used `actual=$(eval "$check_cmd")` with no fallback; under
  `set -e`, a `check_cmd` whose pipeline ends non-zero (a `grep -c` match
  count of zero, in `test-event-sourcing.sh`'s case) kills the whole script
  silently on the very first poll attempt, before it gets a chance to
  retry. Same root cause STR-145 found in the k8s copy of the reservation
  script; present independently in `test-event-sourcing.sh` too. Fixed both
  with `actual=$(eval "$check_cmd" 2>/dev/null) || actual="<poll error,
  retrying>"`.
- `scripts/test-temporal-saga.sh` generated `PRODUCT_A`/`PRODUCT_B` as bare
  `uuid.uuid4()`s that exist in Inventory but not in Catalog — `/checkout/v2`
  looks up each cart product's price from Catalog (unlike the v1 checkout
  the reservation-saga script exercises, which never calls Catalog at all),
  so `GET /products/:id` 404s and the endpoint 500s before a workflow even
  starts. Fixed by actually creating real Catalog products with controlled
  prices (one deliberately not ending in ".99", one deliberately at 12.99 to
  hit Payments' failure simulation deterministically instead of hoping the
  demo seed data happened to contain a ".99"-priced product).
- Same script's workflow-history assertion shelled out to `docker run
  temporalio/admin-tools:1.27.2-tctl-1.18.2-cli-1.1.1`, a pinned tag not
  present locally with no egress to pull it — always failed before reaching
  a real assertion. Fixed by `docker compose exec`-ing into the `temporal`
  service container instead, which already bundles the same CLI; also
  needed `--detailed`, since the default `workflow show` output never prints
  activity names (`reserve_stock`, `charge_payment`, ...), only generic
  event types.
- `test-event-sourcing.sh`'s as-of check built a query string from an
  ISO-8601 timestamp containing a `+00:00` offset without URL-encoding it;
  curl sent the literal `+`, which query-string parsing (this server's
  included) treats as an encoded space, so the server 422'd on the mangled
  timestamp. Fixed by encoding `+` as `%2B`.
- Same script's section 1 hard-assumed the reservation/consumption would
  land on "stock A" specifically, but `commands._allocate` orders candidate
  `StockItem` rows by `ORDER BY StockItem.id` (a random uuid4, unrelated to
  which stock a row lives in) — confirmed live: one real run landed the
  entire reservation on stock B instead, since B's row happened to sort
  first. Fixed by reordering the script's own sequence (reserve before move,
  not after) so stock B's row for that product doesn't exist yet at reserve
  time, making stock A the only possible allocation target — a test-
  sequencing fix, no change to `_allocate` itself (unrelated to STR-149,
  pre-existing allocation-order behavior this ticket doesn't redesign).

With all of the above fixed: `test-reservation-saga.sh` and
`test-temporal-saga.sh` (including its payment-failure/compensation path)
each passed 3 consecutive runs against the same seeded stack, and
`test-event-sourcing.sh` passed 2 consecutive runs against the live
Postgres-backed stack (migrated + newly-generated events both correct via
`history`/`as-of`).

**Concurrent-reservation race condition** (Step 4, the ticket's
highest-priority check): two concurrent `POST /stocks/reserve` requests for
the same `(store, product)` with a stock item seeded to `quantity=1` (enough
for exactly one to succeed), fired via `asyncio.gather` directly at
Inventory's internal endpoint. Observed, across 5 repeated runs: exactly one
request returns `{"status": "reserved"}`, the other returns a clean
`{"status": "insufficient_stock"}` (HTTP 200, not a 500 or silent overcount)
— `stock_events`' `UNIQUE(aggregate_id, sequence_number)` constraint
rejected the loser's stale-sequence append, `run_with_retry` retried it
against freshly-read state, and the retry correctly saw zero stock left.
`check-availability` afterward confirmed `available=0`. Releasing the
winner's reservation and retrying the loser's order succeeds cleanly
(`{"status": "reserved"}`), confirming retry-when-stock-frees-up also works.
No design change needed here — this is the mechanism working exactly as
designed.

## Migrations

New migration after changing `src/inventory/models.py`:

```bash
DATABASE_URL=postgresql+asyncpg://inventory:inventory@localhost:5434/inventory \
  uv run alembic revision --autogenerate -m "describe the change"
```
