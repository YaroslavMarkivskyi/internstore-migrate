# ai-assistant

OpenAI-powered chat agent that answers customer messages in Chat's rooms
while a room is in "AI" mode. No Gateway route — it's a pure background
service, triggered by Kafka, that talks back to Chat/Orders over internal
HTTP. See [docs/EVENT_BROKER.md](../../docs/EVENT_BROKER.md).

## What it does

Consumes `chat-events`' `CustomerMessageSent` (staged by Chat on every
customer/guest message, see
[services/chat/src/chat/ws/room.py](../chat/src/chat/ws/room.py)). For each
one:

1. Reads `chat:{room_id}:mode` from Redis (default `"ai"` if the key is
   missing — matches `rooms.ai_mode`'s own default). Skips if `"human"`.
2. Checks the room's rate limit (`chat:{room_id}:ai_count`, max
   `AI_RATE_LIMIT` per hour). If the room is already at the limit, sends one
   final "switching to human support" message and calls
   `PATCH /rooms/{id}/mode` itself to flip the room to human, instead of
   calling OpenAI.
3. Otherwise builds context (see below), calls OpenAI, and posts the reply
   back into the room via `POST /rooms/{id}/messages` (internal endpoint,
   role `assistant`) — it shows up for every connected client exactly like
   any other message, since that endpoint goes through the same Redis
   pub/sub fanout as a WebSocket-sent one.

Also consumes `catalog-events`' `ProductUpdated` to keep its own
`product_embeddings` table (a separate Postgres database, `ai-db`, with the
pgvector extension) in sync — see
[src/ai_assistant/embeddings.py](src/ai_assistant/embeddings.py).

## Permissions: read-only

This service never modifies an order, product, or inventory row. It reads:

- Conversation history — `GET /rooms/{id}/messages` from Chat.
- Registered customers' recent orders — `GET /orders/admin?owner_id=...`
  from Orders (guests are skipped: there's no order history to look up for
  a session ID, only a Keycloak `sub`; see
  `context.is_registered_customer`).
- Product context — a pgvector similarity search against its own
  `product_embeddings` table, never Catalog's database directly.

The only *write* it ever performs against another service is posting its
own reply into a room, and (on rate limit) flipping that room's mode.

## Authenticating to Chat/Orders

Unlike every other domain service, this one has no inbound REST API for
anyone to call — no Gateway route, so there's no incoming request whose
internal token it could forward (contrast with Orders' calls to Inventory).
Since it's triggered by a Kafka event, not an HTTP request, it mints its
own internal token from the shared `INTERNAL_TOKEN_SECRET` on every
outbound call (`role: "assistant"`) — see
[src/ai_assistant/auth.py](src/ai_assistant/auth.py). Chat and Orders both
had to be taught to accept that role on the specific endpoints this service
calls (`GET /rooms/{id}/messages`, `POST /rooms/{id}/messages`,
`PATCH /rooms/{id}/mode`, `GET /orders/admin`).

## Rate limiting

`chat:{room_id}:ai_count` is a Redis counter, incremented on every reply,
TTL'd to `AI_RATE_LIMIT_WINDOW_SECONDS` (default 3600s) from its first
increment. Capped at `AI_RATE_LIMIT` (default 10) replies per room per
hour — bounds runaway OpenAI spend on an adversarial/spammy conversation.
This is per-room, not per-customer: a customer with several open rooms gets
the limit again in each one.

## Dev gaps (accepted)

- **Requires a real `OPENAI_API_KEY`.** No local LLM fallback — every chat
  completion/embedding call fails without one. Same class of trade-off as
  Notifications' Mailpit stub.
- **Embeddings are built lazily.** `product_embeddings` is empty until
  Catalog publishes `ProductUpdated` for a product (on any `PATCH
  /products/{id}`) — a fresh stack has no RAG context until then. Run
  [scripts/seed-embeddings.sh](../../scripts/seed-embeddings.sh) to trigger
  an initial embed for every existing product.

## Local dev without Docker

```bash
cd services/ai-assistant
cp .env.example .env   # point at a running Postgres (with pgvector)/Kafka/Redis/Chat/Orders, and a real OPENAI_API_KEY
uv sync
uv run alembic upgrade head
uv run uvicorn ai_assistant.main:create_app --factory --reload
```

## Tests

```bash
uv run pytest
```

Everything is tested against mocks — no real Postgres/Kafka/Redis/OpenAI
call is made:

- `test_context.py` — the OpenAI message array assembled from mocked
  Chat/Orders responses and a mocked pgvector search result.
- `test_agent.py` — the OpenAI call's parameters, the mode check (against
  `fakeredis`), and rate-limit enforcement (including the auto-switch-to-
  human fallback).
- `test_embeddings.py` — `ProductUpdated` upserts an embedding correctly
  (both insert and update paths) and skips an already-processed event id;
  similarity search returns the mocked top-N rows.

## End-to-end verification

[scripts/test-ai-assistant.sh](../../scripts/test-ai-assistant.sh) drives a
real customer chat session against the full `docker compose` stack: sends a
message, polls for the AI's reply, toggles to human mode and checks
Mailpit for the `AdminRequested` email, confirms the AI stays silent while
in human mode, then toggles back and confirms it resumes.
