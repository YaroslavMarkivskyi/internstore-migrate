# chat

Real-time WebSocket chat between customers (registered and guest) and admins.
Seventh and final domain service. Technically the most complex: WebSocket
proxying through nginx, Redis pub/sub for horizontal scaling, MinIO for image
attachments, PostgreSQL for chat history.

Same stack as every other domain service: Python/FastAPI/SQLAlchemy
(async)/Alembic, its own Postgres database with zero shared tables, and the
same internal-token verification pattern (see
[src/chat/auth.py](src/chat/auth.py)). New here: `redis` (pub/sub +
presence) and `boto3` (S3-compatible client against MinIO) — no other
service in this repo uses either yet.

## Data model

- `Room` — `id` is the *business key itself* (`room_{user_id}` for a
  registered customer, `room_{session_id}` for a guest), not a UUID
  surrogate. That string is also the WS path segment, the Redis pub/sub
  channel suffix, and the presence-set key — one key, no extra lookup.
  `customer_id`/`session_id` are nullable, exactly one populated.
  `notification_sent_at` gates the offline-admin email (see below).
- `Message` — registered users only (`sender_type: customer|admin`). Guest
  messages are never persisted — ephemeral, lost on disconnect, per the
  ticket.
- `RoomMember` — which admins have opened a room. First admin to open it
  "takes" it; there's no exclusivity, others can join and everyone sees
  everything in real time.
- `OutboxEvent` — transactional outbox, same pattern as
  [services/orders](../orders)'s: staged in the same DB transaction as the
  domain change it announces, published to Kafka's `chat-events` topic by a
  background poller.

## Auth — reuses the existing internal-token trust boundary

Chat does **not** implement its own guest-session validation. Guest chat
access rides on the exact mechanism Orders' cart/checkout already use:
`auth-backend`'s `/auth/verify` looks up the `is_guest_id` cookie against
Redis and mints an `X-Internal-Token` with `role: "guest"` — see
[services/auth-backend/README.md](../auth-backend/README.md#guest-sessions).
`GUEST_ALLOWED_PATH_PREFIXES` in `services/auth-backend/src/index.ts` was
extended to cover `/ws/room` and `/api/chat/rooms` for this. Chat just
verifies `X-Internal-Token` locally like every other service
([src/chat/auth.py](src/chat/auth.py)) and trusts the `role`/`sub` claims —
no direct Redis guest-session lookups here, avoiding a second copy of that
logic.

WebSocket-specific: browsers' native `WebSocket` API can't set an
`Authorization` header on the handshake, so nginx's `/ws/` location accepts
a `?token=` query param as a fallback and forwards it through the same
`auth_request` gate as everything else (see `nginx/nginx.conf`). Either way,
by the time a request reaches this service, `X-Internal-Token` is already
set on the handshake request — `get_internal_claims_ws` in
[src/chat/auth.py](src/chat/auth.py) reads it straight off
`WebSocket.headers`.

Room ownership: a customer/guest may only open `/ws/room/room_{their own
sub}` — attempting another room closes the connection (WS 1008). An admin
may open any room.

## WebSocket flow — Approach 1 (publish-then-fanout)

`GET /ws/room/{room_id}`, implemented in
[src/chat/ws/room.py](src/chat/ws/room.py). This instance never delivers a
received message directly to its own local clients. On every incoming
message it always `PUBLISH`es to Redis first (`chat:{room_id}` channel),
and only delivers — to every local socket in that room, including the
sender's own — when that same message comes back through the Redis
subscription. This guarantees message ordering across however many
instances are running, and doubles as an implicit delivery confirmation:
the sender doesn't know a message "landed" until it round-trips back.

On connect:
1. Room ownership check (above).
2. Lazy-create the `Room` row if it doesn't exist yet.
3. If admin: upsert `RoomMember`, and reset `notification_sent_at` to
   `NULL` — an admin joining means the next batch of offline messages
   should be able to notify again (see below).
4. Register the socket locally; if it's the first local connection for this
   room, subscribe to the room's Redis channel and mark this instance
   present.
5. Registered users (customer/admin) get the last `history_replay_limit`
   messages replayed as a `{"type": "history", "messages": [...]}` frame.
   Guests get nothing here — no persisted history to replay.

On receive: `{"type": "message", "content", "attachment_url"}` is persisted
(registered users only) and published; `{"type": "typing"}` goes straight
to Redis pub/sub with no DB write and no admin-presence bookkeeping — an
in-memory-only signal, per the ticket's documented dev gap.

On disconnect: unregister locally; if this was the last local connection
for the room, unsubscribe from Redis and clear this instance's presence
entry.

### Redis keys

- `chat:{room_id}` — pub/sub channel. **Implementation note**: each active
  room gets its own dedicated `PubSub` connection + listener task (created
  on subscribe, torn down on unsubscribe), not one shared long-lived
  connection with channels added/removed on it — see the docstring in
  [src/chat/pubsub.py](src/chat/pubsub.py) for why (`redis-py`'s
  `PubSub.listen()` runs an internal `while self.subscribed:` loop that
  silently exits the instant a shared connection's channel count hits
  zero, and re-subscribing that same connection afterward isn't reliably
  supported across client implementations).
- `chat:{room_id}:connections` — `SADD`/`SREM`'d with this instance's id on
  first-local-connect/last-local-disconnect. General presence bookkeeping,
  per the ticket.
- `chat:{room_id}:admins` — `SADD`/`SREM`'d with the admin's own id,
  ref-counted locally per instance so a second browser tab from the same
  admin doesn't flip presence off when the first tab closes. Used
  specifically to decide whether to stage the offline-admin notification
  (`SCARD` == 0 check below) — kept separate from the general
  `:connections` set because that one mixes customer and admin sockets.
- Guest sessions: read-only, via `auth-backend`, not touched directly here
  (see Auth above) — no new Redis schema for that.

## Offline admin notification

When a customer/guest sends a message and `SCARD chat:{room_id}:admins ==
0` and `Room.notification_sent_at IS NULL`: stage an `UnreadMessageReceived`
outbox event (same transaction as the message insert) and set
`notification_sent_at`. Subsequent messages in the same unread window don't
re-stage. An admin connecting resets `notification_sent_at` back to `NULL`,
so a *fresh* round of offline messages after that admin has come and gone
can notify again.

Notifications' existing handler
(`services/notifications/src/notifications/templates.py`'s
`unread_message_received`) expects `sender_name` and an optional
`recipient_email`. Chat has no admin directory, so `recipient_email` is
omitted — Notifications falls back to its `OPS_NOTIFICATION_EMAIL` ops
inbox, the same documented gap as Telemetry's `TemperatureThresholdViolated`
event.

## REST endpoints

- `GET /rooms` — admin-only. `unread_count` is approximated as customer
  messages since the most recent admin to join the room (no dedicated
  read-receipt table); `customer_name` is always `null` — no customer
  directory in this service.
- `GET /rooms/{id}/messages?before=<message-id>&limit=50` — admin-only,
  cursor-paginated, newest-first.
- `DELETE /rooms/{id}` — admin-only, removes the room and its messages.
- `POST /rooms/{id}/attachments` — open to any room participant: the admin
  (any room) or the customer/guest whose own `sub` matches the room's
  `customer_id`/`session_id` (403 otherwise). Validates JPEG/PNG, ≤20MB,
  streams to MinIO, returns `{"attachment_url": "..."}`. The client then
  sends that URL back in a WebSocket message's `attachment_url` field.

## MinIO — dev gap

`MinioClient` ([src/chat/minio_client.py](src/chat/minio_client.py)) is a
thin `boto3` S3 client against MinIO's S3-compatible API. Two separate URLs
matter: `MINIO_ENDPOINT` (`http://minio:9000`, the container-network address
this service's boto3 client actually talks to) and
`MINIO_PUBLIC_BASE_URL` (`http://localhost:9000` in dev, host-exposed so a
browser can load `attachment_url` directly). **Documented gap**: in prod
this would be a real S3 bucket behind CloudFront/signed URLs, not a
host-exposed MinIO port — swapping is meant to be a config change
(`MINIO_ENDPOINT`/`MINIO_PUBLIC_BASE_URL`/credentials), not a code change,
since `MinioClient` only talks to the S3-compatible API surface.

## Local dev without Docker

```bash
cd services/chat
cp .env.example .env   # point DATABASE_URL/REDIS_URL/MINIO_* at local instances
uv sync
uv run alembic upgrade head
uv run uvicorn chat.main:create_app --factory --reload
```

Run tests (self-contained: a temp-file-backed SQLite DB per test,
`fakeredis` for Redis, a fake MinIO client swapped in via
`app.dependency_overrides` — no real Postgres/Redis/MinIO/Kafka needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d --build chat-db chat redis minio minio-init nginx
```

Reachable through nginx at `wss://localhost:8443/ws/room/{room_id}` and
`/api/chat/*` (see [nginx/nginx.conf](../../nginx/nginx.conf)) — not
exposed on the host directly. Unlike the other domain services' nginx
locations, `/ws/` and `/api/chat/` use nginx's resolver-based dynamic
`proxy_pass` (a variable, not a static `upstream {}` block) specifically so
`docker compose up --scale chat=2` round-robins across replicas without an
nginx config change or restart — this is the one service the ticket
explicitly calls out needing to support horizontal scaling end-to-end.

End-to-end smoke test:

```bash
docker compose up -d --build
./scripts/test-chat-saga.sh
```

## Migrations

```bash
DATABASE_URL=postgresql+asyncpg://chat:chat@localhost:5436/chat \
  uv run alembic revision --autogenerate -m "describe the change"
```
