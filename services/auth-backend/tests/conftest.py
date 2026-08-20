import json
import time

import fakeredis
import jwt
import pytest
from firebase_admin import auth as firebase_auth
from httpx import ASGITransport, AsyncClient

from auth_backend.config import Settings
from auth_backend.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
FIREBASE_PROJECT_ID = "internstore-test"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


# STR-155: there's no real Firebase project in unit tests, and a genuine
# Firebase ID token can only be produced by Google's own signing keys — so
# rather than hand-rolling a fake JWT and monkeypatching cert fetch, tests
# mock firebase_admin.auth.verify_id_token itself, the exact boundary
# ExternalTokenVerifier calls. The "token" minted here is a small JSON
# envelope _fake_verify_id_token below decodes — it is never a real JWT and
# is never parsed by anything else.
def mint_external_token(
    *,
    sub: str = "11111111-1111-1111-1111-111111111111",
    email: str | None = "customer@example.com",
    role: str | None = "customer",
    expires_in: int = 300,
    revoked: bool = False,
    disabled: bool = False,
) -> str:
    now = int(time.time())
    return json.dumps(
        {
            "sub": sub,
            "email": email,
            "role": role,
            "iat": now,
            "exp": now + expires_in,
            "revoked": revoked,
            "disabled": disabled,
        }
    )


def _fake_verify_id_token(token: str, app=None, check_revoked: bool = False, clock_skew_seconds: int = 0):
    del app, clock_skew_seconds
    try:
        claims = json.loads(token)
    except (TypeError, ValueError) as exc:
        raise firebase_auth.InvalidIdTokenError("Malformed token") from exc

    now = int(time.time())
    if claims.get("exp", 0) < now:
        raise firebase_auth.ExpiredIdTokenError("Token expired", cause=None)
    if claims.get("disabled"):
        raise firebase_auth.UserDisabledError("User disabled")
    # Mirrors Firebase Admin SDK's own _check_jwt_revoked_or_disabled: only
    # consulted when check_revoked=True is passed in, same as the real SDK.
    if check_revoked and claims.get("revoked"):
        raise firebase_auth.RevokedIdTokenError("Token revoked")

    return {
        "uid": claims.get("sub"),
        "email": claims.get("email"),
        "role": claims.get("role"),
        "iat": claims.get("iat"),
        "exp": claims.get("exp"),
    }


@pytest.fixture
def redis() -> fakeredis.aioredis.FakeRedis:
    # An explicit per-test FakeServer() keeps each test's Redis state
    # isolated — a FakeRedis() with no explicit server connects to a shared
    # *global* in-process fake backend, which would leak guest sessions
    # across otherwise-independent tests (same rationale as chat's tests).
    return fakeredis.aioredis.FakeRedis(server=fakeredis.aioredis.FakeServer(), decode_responses=True)


@pytest.fixture
async def client(monkeypatch, redis):
    monkeypatch.setattr(firebase_auth, "verify_id_token", _fake_verify_id_token)

    settings = Settings(
        firebase_project_id=FIREBASE_PROJECT_ID,
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        internal_token_ttl_seconds=60,
        redis_url="redis://redis.invalid:6379",
    )

    # Deliberately not letting the app's real lifespan run (it would build
    # its own Redis client against settings.redis_url, a host that doesn't
    # exist, and call firebase_admin.initialize_app() against Application
    # Default Credentials that don't exist in this environment either) —
    # same as every other service's tests, app.state is populated by hand
    # instead.
    app = create_app(settings=settings)
    app.state.redis = redis
    from auth_backend.auth.external_token import ExternalTokenVerifier
    from auth_backend.auth.guest_session import GuestSessionStore

    app.state.guest_session_store = GuestSessionStore(redis)
    app.state.external_token_verifier = ExternalTokenVerifier()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app
        yield ac
