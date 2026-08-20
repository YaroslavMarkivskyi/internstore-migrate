import httpx
import respx

from orders.authz import AuthzClient


@respx.mock
async def test_check_allows_when_opa_returns_true():
    route = respx.post("http://opa.invalid/v1/data/orders/allow").mock(
        return_value=httpx.Response(200, json={"result": True})
    )

    client = AuthzClient("http://opa.invalid")
    allowed = await client.check(
        subject={"role": "customer", "sub": "cust-1"},
        action="view",
        resource={"type": "order", "owner": "cust-1"},
    )

    assert allowed is True
    assert route.called


@respx.mock
async def test_check_denies_when_opa_returns_false():
    respx.post("http://opa.invalid/v1/data/orders/allow").mock(return_value=httpx.Response(200, json={"result": False}))

    client = AuthzClient("http://opa.invalid")
    allowed = await client.check(
        subject={"role": "customer", "sub": "cust-1"},
        action="view",
        resource={"type": "order", "owner": "cust-2"},
    )

    assert allowed is False


@respx.mock
async def test_check_queries_given_package():
    # `package` is a per-call override, not hardcoded to "orders" -- this
    # only exercises that the client itself is reusable; the only actual
    # production call site is routers/orders.py's get_order, always
    # against the default "orders" package.
    route = respx.post("http://opa.invalid/v1/data/some-other-package/allow").mock(
        return_value=httpx.Response(200, json={"result": True})
    )

    client = AuthzClient("http://opa.invalid")
    allowed = await client.check(
        subject={"role": "customer", "sub": "cust-1"},
        action="view",
        resource={"type": "order"},
        package="some-other-package",
    )

    assert allowed is True
    assert route.called


@respx.mock
async def test_check_fails_closed_when_sidecar_unreachable():
    respx.post("http://opa.invalid/v1/data/orders/allow").mock(side_effect=httpx.ConnectError("connection refused"))

    client = AuthzClient("http://opa.invalid")
    allowed = await client.check(
        subject={"role": "admin", "sub": "admin-1"},
        action="view",
        resource={"type": "order", "owner": "cust-1"},
    )

    # Fail closed: an unreachable sidecar denies, even for a subject who
    # would otherwise be allowed -- never silently falls back to allow.
    assert allowed is False


@respx.mock
async def test_check_fails_closed_on_5xx():
    respx.post("http://opa.invalid/v1/data/orders/allow").mock(return_value=httpx.Response(500))

    client = AuthzClient("http://opa.invalid")
    allowed = await client.check(
        subject={"role": "admin", "sub": "admin-1"},
        action="view",
        resource={"type": "order", "owner": "cust-1"},
    )

    assert allowed is False
