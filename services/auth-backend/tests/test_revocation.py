import time

import httpx
import respx

from auth_backend.auth.revocation import CACHE_TTL_SECONDS, RevocationChecker
from auth_backend.config import Settings
from tests.conftest import mint_external_token

KEYCLOAK_ISSUER = "http://keycloak.invalid/realms/internstore"
INTROSPECT_URL = f"{KEYCLOAK_ISSUER}/protocol/openid-connect/token/introspect"


def _settings() -> Settings:
    return Settings(
        keycloak_issuer=KEYCLOAK_ISSUER,
        keycloak_jwks_uri=f"{KEYCLOAK_ISSUER}/protocol/openid-connect/certs",
        keycloak_client_id="internstore-backend",
        keycloak_client_secret="test-client-secret",
        internal_token_secret="test-secret",
        redis_url="redis://redis.invalid:6379",
    )


@respx.mock
async def test_active_token_is_not_revoked():
    respx.post(INTROSPECT_URL).mock(return_value=httpx.Response(200, json={"active": True}))
    checker = RevocationChecker(_settings())

    assert await checker.is_revoked("some-token") is False


@respx.mock
async def test_inactive_token_is_revoked():
    respx.post(INTROSPECT_URL).mock(return_value=httpx.Response(200, json={"active": False}))
    checker = RevocationChecker(_settings())

    assert await checker.is_revoked("some-token") is True


@respx.mock
async def test_non_200_response_fails_closed():
    respx.post(INTROSPECT_URL).mock(return_value=httpx.Response(500))
    checker = RevocationChecker(_settings())

    assert await checker.is_revoked("some-token") is True


@respx.mock
async def test_unreachable_keycloak_fails_closed():
    respx.post(INTROSPECT_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    checker = RevocationChecker(_settings())

    assert await checker.is_revoked("some-token") is True


@respx.mock
async def test_second_request_for_same_token_hits_cache():
    route = respx.post(INTROSPECT_URL).mock(return_value=httpx.Response(200, json={"active": True}))
    checker = RevocationChecker(_settings())

    await checker.is_revoked("some-token")
    await checker.is_revoked("some-token")

    assert route.call_count == 1


@respx.mock
async def test_cache_expiry_triggers_new_introspection(monkeypatch):
    route = respx.post(INTROSPECT_URL).mock(return_value=httpx.Response(200, json={"active": True}))
    checker = RevocationChecker(_settings())

    fake_now = [1_000.0]
    monkeypatch.setattr(time, "monotonic", lambda: fake_now[0])

    await checker.is_revoked("some-token")
    fake_now[0] += CACHE_TTL_SECONDS + 1
    await checker.is_revoked("some-token")

    assert route.call_count == 2


# The `client` fixture stubs RevocationChecker._introspect wholesale (see
# conftest.py) so tests unrelated to revocation don't need a live Keycloak.
# These two restore the real method so introspection's own fail-closed
# logic — not just main.py's catch-all `except Exception` — is what's
# actually under test here.
_REAL_INTROSPECT = RevocationChecker._introspect


@respx.mock
async def test_verify_returns_401_when_token_revoked(client, monkeypatch, rsa_keypair):
    monkeypatch.setattr(RevocationChecker, "_introspect", _REAL_INTROSPECT)
    respx.post(INTROSPECT_URL).mock(return_value=httpx.Response(200, json={"active": False}))

    private_pem, _ = rsa_keypair
    token = mint_external_token(private_pem)

    resp = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


@respx.mock
async def test_verify_returns_401_when_keycloak_unreachable(client, monkeypatch, rsa_keypair):
    monkeypatch.setattr(RevocationChecker, "_introspect", _REAL_INTROSPECT)
    respx.post(INTROSPECT_URL).mock(side_effect=httpx.ConnectError("connection refused"))

    private_pem, _ = rsa_keypair
    token = mint_external_token(private_pem)

    resp = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401
