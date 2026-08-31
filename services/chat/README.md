# chat

Real-time WebSocket chat between customers (registered and guest) and admins.
Seventh and final domain service. Technically the most complex: WebSocket
proxying through nginx, Redis pub/sub for horizontal scaling, a GCS bucket
for image attachments, PostgreSQL for chat history.

Same stack as every other domain service: Python/FastAPI/SQLAlchemy
(async)/Alembic, its own Postgres database with zero shared tables, and the
same internal-token verification pattern (see
[src/chat/auth.py](src/chat/auth.py)). New here: `redis` (pub/sub +
presence) and `boto3` (S3-compatible client against a GCS bucket) — no
other service in this repo uses either yet.

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
extended to cover `/ws/room` and `/api/chat/rooms` for this.

Chat is a **hybrid** case, same shape as [Orders](../orders#auth):
**chat-gate** (nginx, `auth_request`) sits in front of it, occupying the
network-facing port (`:8000`) the external Gateway's `/ws/` and
`/api/chat/` locations still call, and handles the coarse, route-level
tier:

- **admin** — `GET /rooms` (the admin room list), `DELETE /rooms/{id}`.
- **admin-or-assistant** — `GET /rooms/{id}/messages` (the AI Assistant
  reads recent history to build conversation context).
- **assistant** (not admin-or-assistant — admin does *not* get a bypass
  here) — `POST /rooms/{id}/messages` and `POST /rooms/{id}/messages/stream`,
  the AI Assistant's only ways to inject a message into a room (the latter
  streams the reply in as it's generated — see REST endpoints below).
- **any authenticated caller** — everything else, including the
  `/ws/room/{id}` WebSocket handshake, `GET`/`PATCH /rooms/{id}/mode`,
  and `POST /rooms/{id}/attachments`.

See [nginx/internal-gate/chat.conf](../../nginx/internal-gate/chat.conf)'s
`$chat_auth_tier` map, **chat-verify**
([services/internal-gate](../internal-gate)) and **chat-opa**'s policy
([policies/chat.rego](../../policies/chat.rego)).

What does **not** move to the gate: room-ownership decisions ("is this my
room"). `_room_owner_matches` (`routers/mode.py`, `ws/room.py`) is a pure
function of `room_id` + the caller's own `sub` — no DB lookup needed, so
it just stays inline in the app. `_authorize_room_access`
(`routers/attachments.py`) *does* need a DB lookup (`room.customer_id`/
`room.session_id`), unreachable from the gate, same reasoning as Orders'
`GET /orders/{id}` — it also stays inline, unchanged.

The app no longer verifies the internal token itself either way — it
trusts `X-User-Id`/`X-User-Role`, forwarded by chat-gate once *it* has
verified them (see [src/chat/auth.py](src/chat/auth.py)). This is
identity *extraction*, not verification: safe only because this app is
unreachable on any path except through chat-gate (`HOST=127.0.0.1`, see
docker-compose.yml).

WebSocket-specific: browsers' native `WebSocket` API can't set an
`Authorization` header on the handshake, so nginx's `/ws/` location (the
external Gateway) accepts a `?token=` query param as a fallback and
forwards the resulting `X-Internal-Token` straight through — the
handshake is a plain HTTP GET with an `Upgrade` header, so both the
external Gateway's and chat-gate's `auth_request` work on it exactly like
any REST call. `get_internal_claims_ws` in
[src/chat/auth.py](src/chat/auth.py) reads `X-User-Id`/`X-User-Role`
straight off `WebSocket.headers`, forwarded by chat-gate.

Room ownership: a customer/guest may only open `/ws/room/room_{their own
sub}` — attempting another room closes the connection (WS 1008). An admin
may open any room.

Live verification: [scripts/verify-chat-gate.sh](../../scripts/verify-chat-gate.sh).

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

On receive: `{"type": "message", "content", "attachment_key"}` is persisted
(registered users only, as `attachment_key` — see "Object storage" below)
and published; `{"type": "typing"}` goes straight
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
- `POST /rooms/{id}/messages` — assistant-only, the AI Assistant's plain
  (non-streamed) reply injection: one DB write + one `message` pub/sub frame.
- `POST /rooms/{id}/messages/stream` — assistant-only. Called repeatedly as
  the shopping agent's model produces its answer: a body with `delta` fans
  out a `message_delta` frame (nothing persisted); `reset: true` fans out
  `message_reset` (the model abandoned a partial reply to call a tool);
  `done: true` with the full `content` persists one `Message` and fans out
  `message_done`. Same Redis pub/sub fanout as everything else.
- `POST /rooms/{id}/attachments` — open to any room participant: the admin
  (any room) or the customer/guest whose own `sub` matches the room's
  `customer_id`/`session_id` (403 otherwise). Validates JPEG/PNG, ≤20MB,
  streams to object storage, returns `{"attachment_key": "...", "attachment_url": "..."}`.
  `attachment_key` is what the client sends back in a WebSocket message's
  `attachment_key` field to actually post it into the room (not the URL —
  see below); `attachment_url` there is only a short-lived convenience so
  the client can preview what it just uploaded before sending.

## Object storage — private bucket, signed URLs

`ObjectStorageClient` ([src/chat/object_storage_client.py](src/chat/object_storage_client.py))
is a thin `boto3` client against a GCS bucket over its S3-compatible XML
API + an HMAC key, in every environment including local dev (see
terraform/gcp/modules/storage, or the provisioning `gcloud` commands in
docker-compose.yml). catalog and chat share one bucket, isolated by the
`chat/` vs `catalog/` key prefix (`OBJECT_STORAGE_KEY_PREFIX`). The bucket
is always private (`public_access_prevention = enforced`) — no
public/anonymous read access — so nothing this service returns is a
durable public link.
`Message.attachment_key` (renamed from `attachment_url`) stores only the
object key; every response that includes an `attachment_url`
(`GET /rooms/{id}/messages`, the WS `history` frame, the WS live `message`
publish) signs one fresh from that key on the spot
(`ObjectStorageClient.generate_presigned_url`, short TTL — see
`OBJECT_STORAGE_PRESIGNED_URL_TTL_SECONDS`), never storing it.

`OBJECT_STORAGE_ENDPOINT` and `OBJECT_STORAGE_PUBLIC_BASE_URL` are both
`https://storage.googleapis.com` here (they can differ — the first is what
this service's boto3 client reaches for `put_object`, the second is what a
browser reaches and is used only to *sign* presigned URLs against, since
SigV4 signs the Host itself). Swapping environments is a config change
(`OBJECT_STORAGE_BUCKET`/`OBJECT_STORAGE_KEY_PREFIX`/HMAC credentials), not
a code change, since `ObjectStorageClient` only talks to the S3-compatible
API surface.

## Local dev without Docker

```bash
cd services/chat
cp .env.example .env   # point DATABASE_URL/REDIS_URL/OBJECT_STORAGE_* at local instances
uv sync
uv run alembic upgrade head
uv run uvicorn chat.main:create_app --factory --reload
```

Run tests (self-contained: a temp-file-backed SQLite DB per test,
`fakeredis` for Redis, a fake object-storage client swapped in via
`app.dependency_overrides` — no real Postgres/Redis/GCS/Kafka needed):

```bash
uv run pytest
```

## Via docker compose

```bash
docker compose up -d --build chat chat-opa chat-verify chat-gate chat-db redis kafka nginx
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
