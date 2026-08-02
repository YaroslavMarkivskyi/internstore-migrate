# There is no separate WS route on auth-backend. nginx has a second
# *internal* location (/internal/auth-verify-ws) for the WS handshake that
# calls this exact same /auth/verify route, just with Authorization sourced
# from a ?token= query param instead of a real Authorization header
# (browsers' WebSocket API can't set one on the handshake) — see
# nginx/nginx.conf's $ws_authorization mapping. These tests exercise
# /auth/verify with a bearer token in that same shape, plus the /ws/room
# guest-allowed-path entry specifically.
from tests.conftest import mint_external_token


async def test_verify_accepts_bearer_token_sourced_from_ws_query_param_mapping(client, rsa_keypair):
    private_pem, _ = rsa_keypair
    token = mint_external_token(private_pem)

    # This is exactly what nginx sends for /internal/auth-verify-ws: a
    # normal Authorization header, just built from $arg_token rather than
    # the browser's own header.
    resp = await client.get("/auth/verify", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert resp.headers["X-User-Role"] == "customer"
    assert resp.headers["X-Internal-Token"]


async def test_ws_room_guest_allowed_path_issues_guest_token(client):
    resp = await client.get(
        "/auth/verify",
        headers={"X-Original-URI": "/ws/room/room_guest-session-1"},
    )

    assert resp.status_code == 200
    assert resp.headers["X-User-Role"] == "guest"
    assert resp.headers["X-Internal-Token"]
    assert resp.headers["Set-Cookie"].startswith("is_guest_id=")
