import jwt

from tests.conftest import mint_external_token


async def test_valid_jwt_returns_200_with_internal_token(client, rsa_keypair):
    private_pem, _ = rsa_keypair
    token = mint_external_token(private_pem)

    resp = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.headers["X-User-Role"] == "customer"
    assert resp.headers["X-User-Id"] == "11111111-1111-1111-1111-111111111111"
    internal_token = resp.headers["X-Internal-Token"]
    assert internal_token
    header = jwt.get_unverified_header(internal_token)
    assert header["alg"] == "HS256"


async def test_expired_jwt_returns_401(client, rsa_keypair):
    private_pem, _ = rsa_keypair
    token = mint_external_token(private_pem, expires_in=-10)

    resp = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


async def test_invalid_signature_returns_401(client, other_private_key):
    token = mint_external_token(other_private_key)

    resp = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


async def test_wrong_issuer_returns_401(client, rsa_keypair):
    private_pem, _ = rsa_keypair
    token = mint_external_token(private_pem, issuer="http://keycloak.invalid/realms/other-realm")

    resp = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 401


async def test_guest_allowed_path_without_token_issues_guest_token(client):
    resp = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/api/orders/checkout"},
    )

    assert resp.status_code == 200
    assert resp.headers["X-User-Role"] == "guest"
    assert resp.headers["X-User-Id"]
    assert resp.headers["X-Internal-Token"]
    set_cookie = resp.headers["Set-Cookie"]
    assert set_cookie.startswith("is_guest_id=")
    assert "HttpOnly" in set_cookie
    # Must be "none": the frontend and this gateway differ in scheme
    # (http://localhost:5180 vs https://localhost:8443), which browsers'
    # schemeful-same-site logic treats as cross-site -- a Lax cookie would
    # never be attached to the frontend's actual fetch/XHR calls.
    assert "samesite=none" in set_cookie.lower()


async def test_catalog_browsing_without_token_issues_guest_token(client):
    resp = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/api/catalog/products"},
    )

    assert resp.status_code == 200
    assert resp.headers["X-User-Role"] == "guest"


async def test_non_guest_path_without_token_returns_401(client):
    # Order history is deliberately excluded from the guest allowlist — a
    # guest can browse and check out but must log in to see past orders.
    resp = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/api/orders/orders"},
    )

    assert resp.status_code == 401


async def test_no_token_and_no_original_uri_returns_401(client):
    resp = await client.get("/auth/verify")

    assert resp.status_code == 401
