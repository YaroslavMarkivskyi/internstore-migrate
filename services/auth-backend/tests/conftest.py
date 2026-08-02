import time

import fakeredis
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

from auth_backend.auth.revocation import RevocationChecker
from auth_backend.config import Settings
from auth_backend.main import create_app

INTERNAL_TOKEN_SECRET = "test-secret"
KEYCLOAK_ISSUER = "http://keycloak.invalid/realms/internstore"
ISSUER = "internstore-gateway"


def mint_internal_token(sub: str, role: str) -> str:
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


@pytest.fixture(scope="session")
def rsa_keypair() -> tuple[bytes, bytes]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def other_private_key() -> bytes:
    """An unrelated private key — used to sign tokens with the "wrong" key
    so tests can assert an invalid-signature token is rejected."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def mint_external_token(
    private_pem: bytes,
    *,
    sub: str = "11111111-1111-1111-1111-111111111111",
    email: str = "customer@example.com",
    role: str = "customer",
    issuer: str = KEYCLOAK_ISSUER,
    expires_in: int = 300,
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "email": email,
        "iss": issuer,
        "iat": now,
        "exp": now + expires_in,
        "realm_access": {"roles": [role]},
    }
    return jwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def redis() -> fakeredis.aioredis.FakeRedis:
    # An explicit per-test FakeServer() keeps each test's Redis state
    # isolated — a FakeRedis() with no explicit server connects to a shared
    # *global* in-process fake backend, which would leak guest sessions
    # across otherwise-independent tests (same rationale as chat's tests).
    return fakeredis.aioredis.FakeRedis(server=fakeredis.aioredis.FakeServer(), decode_responses=True)


@pytest.fixture
async def client(monkeypatch, redis, rsa_keypair):
    _private_pem, public_pem = rsa_keypair

    # There's no real Keycloak/JWKS endpoint in unit tests. Monkeypatching
    # PyJWKClient.get_signing_key_from_jwt (rather than mocking the HTTP
    # fetch or hand-building a JWKS document) exercises our own verifier
    # logic — issuer/role/sub checks, expiry, signature — without also
    # having to re-implement JWKS key selection; that part is PyJWT's own
    # responsibility and already covered by its test suite.
    class _FakeSigningKey:
        def __init__(self, key: bytes) -> None:
            self.key = key

    monkeypatch.setattr(
        jwt.PyJWKClient,
        "get_signing_key_from_jwt",
        lambda self, token: _FakeSigningKey(public_pem),
    )

    # No real Keycloak introspection endpoint in unit tests either — default
    # every token to "active" so tests unrelated to revocation don't depend
    # on Keycloak reachability. test_revocation.py overrides this per test
    # (via the same `monkeypatch` fixture) to exercise the revoked /
    # unreachable / cached paths.
    async def _default_introspect(self: RevocationChecker, token: str) -> bool:
        del self, token
        return False

    monkeypatch.setattr(RevocationChecker, "_introspect", _default_introspect)

    settings = Settings(
        keycloak_issuer=KEYCLOAK_ISSUER,
        keycloak_jwks_uri="http://keycloak.invalid/realms/internstore/protocol/openid-connect/certs",
        keycloak_client_id="test-client",
        keycloak_client_secret="test-client-secret",
        internal_token_secret=INTERNAL_TOKEN_SECRET,
        internal_token_ttl_seconds=60,
        redis_url="redis://redis.invalid:6379",
    )

    # Deliberately not letting the app's real lifespan run (it would build
    # its own Redis client against settings.redis_url, a host that doesn't
    # exist) — same as every other service's tests, app.state is populated
    # by hand instead.
    app = create_app(settings=settings)
    app.state.redis = redis
    from auth_backend.auth.external_token import ExternalTokenVerifier
    from auth_backend.auth.guest_session import GuestSessionStore

    app.state.guest_session_store = GuestSessionStore(redis)
    app.state.revocation_checker = RevocationChecker(settings)
    app.state.external_token_verifier = ExternalTokenVerifier(settings.keycloak_issuer, settings.keycloak_jwks_uri)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        ac.app = app
        yield ac
