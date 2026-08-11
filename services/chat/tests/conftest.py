import contextlib

import anyio.from_thread
import fakeredis
import jwt
import pytest
import sqlalchemy
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from chat.config import Settings
from chat.db import Base, make_session_factory
from chat.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


class FakeMinioClient:
    """Swapped in via app.dependency_overrides — no real MinIO/S3 call is
    made. Returns a deterministic URL and records what was uploaded."""

    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []

    async def put_object(self, key: str, body: bytes, content_type: str) -> str:
        self.uploads.append((key, body, content_type))
        return f"http://minio.invalid/chat-attachments/{key}"


@pytest.fixture
def fake_minio_client() -> FakeMinioClient:
    return FakeMinioClient()


@pytest.fixture
async def app_and_client(fake_minio_client: FakeMinioClient, tmp_path):
    # A file-backed DB, not sqlite+aiosqlite:///:memory: — an in-memory
    # sqlite DB forces SQLAlchemy to use StaticPool (a single shared
    # connection), which breaks the moment two different asyncio event
    # loops touch it. WS tests need that: FastAPI's TestClient runs the
    # WebSocket route handler on its own background thread/event loop,
    # separate from the pytest-asyncio loop the test function and the
    # plain `client` (httpx.AsyncClient + ASGITransport) fixture run on. A
    # temp file avoids StaticPool, so each loop gets its own connection
    # against the same durable file.
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        kafka_bootstrap_servers="kafka.invalid:9092",
        redis_url="redis://redis.invalid:6379",
        minio_endpoint="http://minio.invalid:9000",
        minio_public_base_url="http://minio.invalid:9000",
        minio_access_key="test",
        minio_secret_key="test",
        ai_assistant_service_url="http://ai-assistant.invalid",
    )
    session_factory = make_session_factory(settings.database_url)

    engine = session_factory.kw["bind"]

    # WAL mode gives readers on one connection a consistent, prompt view of
    # commits made on another — SQLite's default rollback-journal mode can
    # otherwise leave a short window where a freshly-committed row isn't
    # yet visible to a different connection, which these tests hit more
    # than production code ever would (WS tests deliberately open several
    # separate connections in quick succession, one per portal/thread).
    @sqlalchemy.event.listens_for(engine.sync_engine, "connect")
    def _set_wal_mode(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app(settings=settings)
    app.state.session_factory = session_factory
    # fakeredis stands in for a real Redis instance — no real network I/O,
    # but the same redis.asyncio API surface this service uses (pub/sub +
    # SADD/SREM/SCARD presence sets). A FakeRedis() with no explicit server
    # connects to a shared *global* in-process fake backend, which leaks
    # pub/sub subscriptions and presence-set state across otherwise
    # independent tests — an explicit per-test FakeServer() keeps each
    # test's Redis state isolated, same as the fresh sqlite file above.
    app.state.redis = fakeredis.aioredis.FakeRedis(server=fakeredis.aioredis.FakeServer(), decode_responses=True)
    from chat.pubsub import PubSubRouter

    app.state.pubsub = PubSubRouter(app.state.redis, app.state.ws_manager)
    app.state.minio_client = fake_minio_client
    # STR-146: real AIAssistantClient does a live httpx call to
    # ai_assistant_service_url — swapped for a mock so WS tests that send a
    # customer message don't attempt real network I/O (or block on a DNS
    # timeout against the deliberately-invalid host above) via the
    # fire-and-forget asyncio.create_task in ws/room.py.
    from unittest.mock import AsyncMock

    app.state.ai_assistant_client = AsyncMock()

    from chat.minio_dep import get_minio_client

    app.dependency_overrides[get_minio_client] = lambda: fake_minio_client

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app
        yield app, ac

    # Deliberately not calling app.state.pubsub.close()/redis.aclose() here:
    # any per-room listener tasks PubSubRouter.subscribe() spawned live on
    # ws_client's shared portal loop (see below), which — thanks to fixture
    # teardown ordering (ws_client depends on app, so its teardown runs
    # first) — is already closed by the time this runs. Awaiting/cancelling
    # a Task that belongs to an event loop this code isn't running on is
    # itself undefined behavior and was observed to raise a spurious
    # CancelledError here; the portal's own shutdown already cancels
    # everything scheduled on it, so there's nothing left to clean up.
    await engine.dispose()


@pytest.fixture
async def client(app_and_client):
    _app, ac = app_and_client
    yield ac


@pytest.fixture
async def app(app_and_client):
    the_app, _ac = app_and_client
    yield the_app


@pytest.fixture
def ws_client(app):
    # Deliberately not `with TestClient(app) as client:` — that runs the
    # real lifespan, which starts a Kafka producer against the fake
    # bootstrap server. WS route handlers only touch
    # app.state.{session_factory,redis,pubsub,ws_manager}, all of which
    # create_app() already sets synchronously, so lifespan startup isn't
    # needed for these tests.
    #
    # But `with TestClient(...)` also does something else that matters a
    # lot here: it sets client.portal to one shared anyio blocking portal
    # (one background thread + event loop) reused for every request. Skip
    # that and TestClient's `_portal_factory` falls back to spinning up a
    # *brand new* portal (thread + loop) for every individual
    # websocket_connect() call. That's invisible for tests with a single
    # WS connection, but the moment a test opens two connections into the
    # same room at once (e.g. a customer and an admin), their WS route
    # handlers end up running on two *different* event loops while sharing
    # one FastAPI app instance — including app.state.ws_manager's
    # asyncio.Lock(), which was created on a third loop again (this
    # fixture's). asyncio.Lock/Task objects aren't safe to touch from a
    # loop other than the one that created them; races there manifest as
    # the whole test hanging (reproduced consistently locally). Manually
    # installing one shared portal — the same thing `with TestClient(...)`
    # does — sidesteps that without paying for a real lifespan.
    client = TestClient(app)
    with anyio.from_thread.start_blocking_portal(**client.async_backend) as portal:
        client.portal = portal
        yield client
    client.portal = None
    client.close()


@contextlib.contextmanager
def ws_connect(ws_client: TestClient, room_id: str, token: str, *, is_guest: bool = False):
    """Connects and, for registered users (customer/admin), drains the
    "history" frame the server sends immediately on connect (see
    chat/ws/room.py's _send_history) before handing control back to the
    test — callers shouldn't have to know that frame exists unless a test
    is specifically about history replay (see test_messages.py)."""
    with ws_client.websocket_connect(f"/ws/room/{room_id}", headers={"x-internal-token": token}) as ws:
        if not is_guest:
            ws.receive_text()
        yield ws


@pytest.fixture
def admin_token() -> str:
    return mint_internal_token(sub="admin-1", role="admin")


@pytest.fixture
def customer_token() -> str:
    return mint_internal_token(sub="11111111-1111-1111-1111-111111111111", role="customer")


@pytest.fixture
def guest_token() -> str:
    return mint_internal_token(sub="guest-session-1", role="guest")
