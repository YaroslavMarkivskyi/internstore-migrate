from auth_backend.auth.guest_session import GUEST_SESSION_TTL_SECONDS, KEY_PREFIX


def _extract_cookie_value(set_cookie: str, name: str) -> str:
    first_pair = set_cookie.split(";")[0]
    cookie_name, _, value = first_pair.partition("=")
    assert cookie_name == name
    return value


async def test_first_hit_creates_guest_session(client, redis):
    resp = await client.get("/auth/verify", headers={"X-Original-URI": "/api/orders/cart"})

    assert resp.status_code == 200
    guest_id = resp.headers["X-User-Id"]
    cookie_value = _extract_cookie_value(resp.headers["Set-Cookie"], "is_guest_id")
    assert cookie_value == guest_id

    key = KEY_PREFIX + guest_id
    assert await redis.get(key) == "1"
    ttl = await redis.ttl(key)
    assert 0 < ttl <= GUEST_SESSION_TTL_SECONDS
    assert ttl > GUEST_SESSION_TTL_SECONDS - 60


async def test_renewal_with_existing_cookie_reuses_guest_id(client):
    first = await client.get("/auth/verify", headers={"X-Original-URI": "/api/orders/cart"})
    guest_id = first.headers["X-User-Id"]
    cookie_value = _extract_cookie_value(first.headers["Set-Cookie"], "is_guest_id")

    second = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/api/orders/checkout", "Cookie": f"is_guest_id={cookie_value}"},
    )

    assert second.status_code == 200
    assert second.headers["X-User-Id"] == guest_id
    # No new session was minted on renewal — no Set-Cookie header at all.
    assert "Set-Cookie" not in second.headers


async def test_guest_allowed_on_checkout_v2(client, redis):
    # STR-139: "/api/orders/checkout" 's prefix match already covers the
    # Temporal-orchestrated "/api/orders/checkout/v2" path with no separate
    # allowlist entry — see main.py's GUEST_ALLOWED_PATH_PREFIXES comment.
    resp = await client.get("/auth/verify", headers={"X-Original-URI": "/api/orders/checkout/v2"})

    assert resp.status_code == 200
    assert resp.headers["X-User-Role"] == "guest"


async def test_guest_can_start_payment_intent_for_own_order(client):
    resp = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/api/orders/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6/payment-intent"},
    )
    assert resp.status_code == 200


async def test_guest_cannot_list_order_history(client):
    resp = await client.get("/auth/verify", headers={"X-Original-URI": "/api/orders/orders"})
    assert resp.status_code == 401


async def test_guest_cannot_get_single_order(client):
    resp = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/api/orders/orders/3fa85f64-5717-4562-b3fc-2c963f66afa6"},
    )
    assert resp.status_code == 401


async def test_unknown_cookie_mints_a_fresh_guest_id(client):
    resp = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/api/orders/cart", "Cookie": "is_guest_id=does-not-exist"},
    )

    assert resp.status_code == 200
    assert resp.headers["X-User-Id"] != "does-not-exist"
    assert "Set-Cookie" in resp.headers
