import time

import jwt

from tests.conftest import INTERNAL_TOKEN_SECRET, ISSUER, mint_internal_token


def _mint_expiring_token(sub: str, role: str, *, expires_in: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "role": role, "iss": ISSUER, "iat": now, "exp": now + expires_in},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )


async def test_refresh_reissues_same_identity_with_fresh_exp(client):
    old_token = _mint_expiring_token("customer-1", "customer", expires_in=60)

    resp = await client.post("/auth/refresh", headers={"X-Internal-Token": old_token})

    assert resp.status_code == 200
    new_token = resp.json()["internalToken"]
    payload = jwt.decode(new_token, INTERNAL_TOKEN_SECRET, algorithms=["HS256"], issuer=ISSUER)
    assert payload["sub"] == "customer-1"
    assert payload["role"] == "customer"
    assert payload["exp"] > int(time.time())


async def test_refresh_rejects_expired_token(client):
    expired_token = _mint_expiring_token("customer-1", "customer", expires_in=-10)

    resp = await client.post("/auth/refresh", headers={"X-Internal-Token": expired_token})

    assert resp.status_code == 401


async def test_refresh_rejects_missing_token(client):
    resp = await client.post("/auth/refresh")

    assert resp.status_code == 401


async def test_refresh_rejects_wrong_secret(client):
    bad_token = jwt.encode(
        {"sub": "customer-1", "role": "customer", "iss": ISSUER}, "wrong-secret", algorithm="HS256"
    )

    resp = await client.post("/auth/refresh", headers={"X-Internal-Token": bad_token})

    assert resp.status_code == 401


async def test_refresh_rejects_no_exp_token(client):
    # mcp-gateway/ai-assistant's own self-minted tokens have no exp claim at
    # all (see services/mcp_gateway/auth.py) — this is a different code path
    # (they mint their own identity outright rather than refreshing) and
    # isn't expected to hit this endpoint, but a token missing sub/role
    # entirely should still be rejected like any other malformed claim set.
    token = mint_internal_token(sub="", role="customer")

    resp = await client.post("/auth/refresh", headers={"X-Internal-Token": token})

    assert resp.status_code == 401
