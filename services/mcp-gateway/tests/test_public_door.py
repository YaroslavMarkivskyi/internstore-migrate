"""Phase 3 — the public MCP door: a co-located OAuth 2.1 Authorization
Server (identity federated to Firebase), and the resource-server side that
caps every public caller at the customer tool tier.

The tests run the full spec dance (DCR -> /authorize -> login -> code ->
/token) against the in-process app, with Firebase sign-in mocked.
"""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

import pytest
from mcp_gateway.oauth.firebase import FirebaseIdentity

from tests.conftest import mcp_session, mint_internal_token

REDIRECT_URI = "http://localhost:9876/callback"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


async def _oauth_access_token(app, client, *, role: str) -> str:
    """Drive DCR + authorization-code + PKCE end to end, return the access token."""
    app.state.oauth.firebase.sign_in = _fake_sign_in(role)

    reg = await client.post(
        "/register",
        json={"redirect_uris": [REDIRECT_URI], "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]},
    )
    assert reg.status_code == 201, reg.text
    client_id = reg.json()["client_id"]

    verifier, challenge = _pkce()
    authz = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": "mcp:shopping",
            "state": "st-123",
        },
    )
    assert authz.status_code == 302
    rid = parse_qs(urlparse(authz.headers["location"]).query)["rid"][0]

    login = await client.post("/oauth/login", data={"rid": rid, "email": "c@example.com", "password": "pw"})
    assert login.status_code == 302
    cb = parse_qs(urlparse(login.headers["location"]).query)
    assert cb["state"] == ["st-123"]
    code = cb["code"][0]

    tok = await client.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )
    assert tok.status_code == 200, tok.text
    body = tok.json()
    assert body["token_type"] == "Bearer" and body["scope"] == "mcp:shopping"
    return body["access_token"]


def _fake_sign_in(role: str):
    async def _sign_in(email: str, password: str) -> FirebaseIdentity:
        return FirebaseIdentity(sub=f"{role}-uid-1", email=email, role=role)

    return _sign_in


async def test_discovery_metadata_is_unauthenticated_and_self_hosted(client):
    prm = await client.get("/.well-known/oauth-protected-resource/mcp")
    assert prm.status_code == 200
    assert prm.json()["authorization_servers"] == ["https://localhost:8443/"]

    asm = await client.get("/.well-known/oauth-authorization-server")
    assert asm.status_code == 200
    meta = asm.json()
    assert meta["authorization_endpoint"] == "https://localhost:8443/authorize"
    assert meta["token_endpoint"] == "https://localhost:8443/token"
    assert "registration_endpoint" in meta

    jwks = await client.get("/.well-known/jwks.json")
    assert jwks.status_code == 200 and jwks.json()["keys"][0]["kty"] == "RSA"


async def test_full_oauth_flow_then_customer_tools_only(app, client):
    token = await _oauth_access_token(app, client, role="customer")
    async with mcp_session(app, None, extra_headers={"Authorization": f"Bearer {token}"}) as session:
        names = {t.name for t in (await session.list_tools()).tools}
    assert {"get_cart", "add_to_cart", "search_products", "search_help"} <= names
    assert not (names & {"get_visit_log", "get_pending_orders", "get_active_incidents"})


async def test_admin_logging_in_through_the_public_door_still_only_gets_customer_tools(app, client):
    token = await _oauth_access_token(app, client, role="admin")
    async with mcp_session(app, None, extra_headers={"Authorization": f"Bearer {token}"}) as session:
        names = {t.name for t in (await session.list_tools()).tools}
    assert "get_cart" in names
    assert not (names & {"get_visit_log", "get_active_users", "get_pending_orders"})


async def test_a_bogus_bearer_is_rejected(app):
    with pytest.raises(Exception):  # noqa: B017 - the mcp client wraps the 401
        async with mcp_session(app, None, extra_headers={"Authorization": "Bearer not-a-real-token"}) as session:
            await session.list_tools()


async def test_the_internal_door_still_works_unchanged(app):
    async with mcp_session(app, mint_internal_token("admin-1", "admin")) as session:
        names = {t.name for t in (await session.list_tools()).tools}
    assert "get_visit_log" in names  # internal admin token -> full ops tier
