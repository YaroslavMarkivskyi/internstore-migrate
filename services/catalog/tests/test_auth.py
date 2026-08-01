import jwt
import pytest

from tests.conftest import INTERNAL_TOKEN_SECRET, ISSUER, mint_internal_token


# STR-118: role-based authorization proof on a real admin-only endpoint.
# customer-token -> 403, admin-token -> 201.
async def test_post_categories_customer_403_admin_201(client, customer_token, admin_token):
    customer_resp = await client.post(
        "/categories",
        json={"name": "Frozen"},
        headers={"x-internal-token": customer_token},
    )
    assert customer_resp.status_code == 403

    admin_resp = await client.post(
        "/categories",
        json={"name": "Frozen"},
        headers={"x-internal-token": admin_token},
    )
    assert admin_resp.status_code == 201


async def test_bad_signature_rejected(client):
    forged = jwt.encode({"sub": "attacker", "role": "admin", "iss": ISSUER}, "wrong-secret", algorithm="HS256")
    resp = await client.post(
        "/categories",
        json={"name": "Frozen"},
        headers={"x-internal-token": forged},
    )
    assert resp.status_code == 401


async def test_wrong_issuer_rejected(client, admin_token):
    forged = jwt.encode(
        {"sub": "admin-1", "role": "admin", "iss": "someone-else"},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )
    resp = await client.post(
        "/categories",
        json={"name": "Frozen"},
        headers={"x-internal-token": forged},
    )
    assert resp.status_code == 401


async def test_expired_token_rejected(client):
    import time

    expired = jwt.encode(
        {"sub": "admin-1", "role": "admin", "iss": ISSUER, "exp": int(time.time()) - 10},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )
    resp = await client.post(
        "/categories",
        json={"name": "Frozen"},
        headers={"x-internal-token": expired},
    )
    assert resp.status_code == 401
