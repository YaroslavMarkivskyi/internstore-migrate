import jwt

from tests.conftest import INTERNAL_TOKEN_SECRET, ISSUER, create_stock


# Role-based authorization proof on a real admin-only endpoint, mirroring
# catalog's STR-118 pattern: customer-token -> 403, admin-token -> 201.
async def test_post_stock_items_customer_403_admin_201(client, customer_token, admin_token):
    stock_id = await create_stock(client)

    customer_resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": "11111111-1111-1111-1111-111111111111", "quantity": 1},
        headers={"x-internal-token": customer_token},
    )
    assert customer_resp.status_code == 403

    admin_resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": "11111111-1111-1111-1111-111111111111", "quantity": 1},
        headers={"x-internal-token": admin_token},
    )
    assert admin_resp.status_code == 201


async def test_bad_signature_rejected(client):
    stock_id = await create_stock(client)
    forged = jwt.encode({"sub": "attacker", "role": "admin", "iss": ISSUER}, "wrong-secret", algorithm="HS256")
    resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": "11111111-1111-1111-1111-111111111111", "quantity": 1},
        headers={"x-internal-token": forged},
    )
    assert resp.status_code == 401


async def test_wrong_issuer_rejected(client):
    stock_id = await create_stock(client)
    forged = jwt.encode(
        {"sub": "admin-1", "role": "admin", "iss": "someone-else"},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )
    resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": "11111111-1111-1111-1111-111111111111", "quantity": 1},
        headers={"x-internal-token": forged},
    )
    assert resp.status_code == 401


async def test_expired_token_rejected(client):
    import time

    stock_id = await create_stock(client)
    expired = jwt.encode(
        {"sub": "admin-1", "role": "admin", "iss": ISSUER, "exp": int(time.time()) - 10},
        INTERNAL_TOKEN_SECRET,
        algorithm="HS256",
    )
    resp = await client.post(
        f"/stocks/{stock_id}/items",
        json={"product_id": "11111111-1111-1111-1111-111111111111", "quantity": 1},
        headers={"x-internal-token": expired},
    )
    assert resp.status_code == 401
