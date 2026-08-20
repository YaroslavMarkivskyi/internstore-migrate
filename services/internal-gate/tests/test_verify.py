import json

import httpx
import respx


async def test_missing_token_rejected(client):
    resp = await client.get("/verify")
    assert resp.status_code == 401


@respx.mock
async def test_allowed_returns_200_with_user_headers(client):
    respx.post("http://opa.invalid/v1/data/catalog").mock(
        return_value=httpx.Response(200, json={"result": {"allow": True, "subject": {"sub": "admin-1", "role": "admin"}}})
    )

    resp = await client.get("/verify", headers={"X-Internal-Token": "admin-token", "X-Original-Method": "POST"})

    assert resp.status_code == 200
    assert resp.headers["X-User-Id"] == "admin-1"
    assert resp.headers["X-User-Role"] == "admin"


@respx.mock
async def test_denied_role_returns_403(client):
    respx.post("http://opa.invalid/v1/data/catalog").mock(
        return_value=httpx.Response(
            200, json={"result": {"allow": False, "subject": {"sub": "cust-1", "role": "customer"}}}
        )
    )

    resp = await client.get("/verify", headers={"X-Internal-Token": "customer-token", "X-Original-Method": "POST"})

    assert resp.status_code == 403


@respx.mock
async def test_unverifiable_token_returns_401_not_403(client):
    # OPA's `subject` rule is undefined for a forged/expired/wrong-issuer
    # token -- absent from the result, distinct from "verified but denied".
    respx.post("http://opa.invalid/v1/data/catalog").mock(return_value=httpx.Response(200, json={"result": {"allow": False}}))

    resp = await client.get("/verify", headers={"X-Internal-Token": "forged-token", "X-Original-Method": "POST"})

    assert resp.status_code == 401


@respx.mock
async def test_opa_unreachable_fails_closed(client):
    respx.post("http://opa.invalid/v1/data/catalog").mock(side_effect=httpx.ConnectError("connection refused"))

    resp = await client.get("/verify", headers={"X-Internal-Token": "admin-token", "X-Original-Method": "POST"})

    assert resp.status_code == 401


@respx.mock
async def test_opa_5xx_fails_closed(client):
    respx.post("http://opa.invalid/v1/data/catalog").mock(return_value=httpx.Response(500))

    resp = await client.get("/verify", headers={"X-Internal-Token": "admin-token", "X-Original-Method": "POST"})

    assert resp.status_code == 401


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


@respx.mock
async def test_required_role_header_forwarded_to_opa_input(client):
    route = respx.post("http://opa.invalid/v1/data/catalog").mock(
        return_value=httpx.Response(200, json={"result": {"allow": True, "subject": {"sub": "cust-1", "role": "customer"}}})
    )

    resp = await client.get(
        "/verify",
        headers={"X-Internal-Token": "customer-token", "X-Original-Method": "POST", "X-Required-Role": "any"},
    )

    assert resp.status_code == 200
    body = json.loads(route.calls.last.request.content)
    assert body["input"]["required_role"] == "any"


@respx.mock
async def test_required_role_header_omitted_when_not_sent(client):
    route = respx.post("http://opa.invalid/v1/data/catalog").mock(
        return_value=httpx.Response(200, json={"result": {"allow": True, "subject": {"sub": "admin-1", "role": "admin"}}})
    )

    resp = await client.get("/verify", headers={"X-Internal-Token": "admin-token", "X-Original-Method": "POST"})

    assert resp.status_code == 200
    body = json.loads(route.calls.last.request.content)
    assert "required_role" not in body["input"]
