import httpx
import respx

from catalog.authz import AuthzClient


@respx.mock
async def test_check_allows_when_opa_returns_true():
    route = respx.post("http://opa.invalid/v1/data/catalog").mock(
        return_value=httpx.Response(200, json={"result": {"allow": True, "subject": {"sub": "admin-1", "role": "admin"}}})
    )

    client = AuthzClient("http://opa.invalid")
    result = await client.check(
        token="admin-token",
        action="create",
        resource={"type": "product"},
    )

    assert result.allowed is True
    assert result.subject == {"sub": "admin-1", "role": "admin"}
    assert route.called
    body = route.calls.last.request.content
    assert b'"action":"create"' in body
    assert b'"token":"admin-token"' in body


@respx.mock
async def test_check_denies_when_opa_returns_false_but_subject_verified():
    respx.post("http://opa.invalid/v1/data/catalog").mock(
        return_value=httpx.Response(
            200, json={"result": {"allow": False, "subject": {"sub": "cust-1", "role": "customer"}}}
        )
    )

    client = AuthzClient("http://opa.invalid")
    result = await client.check(
        token="customer-token",
        action="create",
        resource={"type": "product"},
    )

    assert result.allowed is False
    # A verified-but-wrong-role subject is still surfaced, so the caller
    # can tell this apart from "token never verified" (401 vs 403).
    assert result.subject == {"sub": "cust-1", "role": "customer"}


@respx.mock
async def test_check_has_no_subject_when_token_never_verified():
    # OPA's `subject` rule is undefined for a forged/expired/wrong-issuer
    # token, so it's simply absent from the package's result.
    respx.post("http://opa.invalid/v1/data/catalog").mock(return_value=httpx.Response(200, json={"result": {"allow": False}}))

    client = AuthzClient("http://opa.invalid")
    result = await client.check(
        token="forged-token",
        action="create",
        resource={"type": "product"},
    )

    assert result.allowed is False
    assert result.subject is None


@respx.mock
async def test_check_fails_closed_when_sidecar_unreachable():
    respx.post("http://opa.invalid/v1/data/catalog").mock(side_effect=httpx.ConnectError("connection refused"))

    client = AuthzClient("http://opa.invalid")
    result = await client.check(
        token="admin-token",
        action="create",
        resource={"type": "product"},
    )

    # Fail closed: an unreachable sidecar denies, even for a subject who
    # would otherwise be allowed -- never silently falls back to allow.
    assert result.allowed is False
    assert result.subject is None


@respx.mock
async def test_check_fails_closed_on_timeout():
    respx.post("http://opa.invalid/v1/data/catalog").mock(side_effect=httpx.TimeoutException("timed out"))

    client = AuthzClient("http://opa.invalid")
    result = await client.check(
        token="admin-token",
        action="create",
        resource={"type": "product"},
    )

    assert result.allowed is False


@respx.mock
async def test_check_fails_closed_on_5xx():
    respx.post("http://opa.invalid/v1/data/catalog").mock(return_value=httpx.Response(500))

    client = AuthzClient("http://opa.invalid")
    result = await client.check(
        token="admin-token",
        action="create",
        resource={"type": "product"},
    )

    assert result.allowed is False


@respx.mock
async def test_check_queries_given_package():
    route = respx.post("http://opa.invalid/v1/data/checkout").mock(
        return_value=httpx.Response(200, json={"result": {"allow": True, "subject": {"sub": "cust-1", "role": "customer"}}})
    )

    client = AuthzClient("http://opa.invalid")
    result = await client.check(
        token="customer-token",
        action="checkout",
        resource={"type": "cart"},
        package="checkout",
    )

    assert result.allowed is True
    assert route.called


@respx.mock
async def test_identify_returns_subject_when_opa_verifies():
    respx.post("http://opa.invalid/v1/data/common/subject").mock(
        return_value=httpx.Response(200, json={"result": {"sub": "admin-1", "role": "admin"}})
    )

    client = AuthzClient("http://opa.invalid")
    subject = await client.identify("some-token")

    assert subject == {"sub": "admin-1", "role": "admin"}


@respx.mock
async def test_identify_returns_none_for_unverifiable_token():
    # OPA's `subject` rule is undefined for a forged/expired/wrong-issuer
    # token -- the REST API represents an undefined rule as an empty body.
    respx.post("http://opa.invalid/v1/data/common/subject").mock(return_value=httpx.Response(200, json={}))

    client = AuthzClient("http://opa.invalid")
    subject = await client.identify("forged-token")

    assert subject is None


@respx.mock
async def test_identify_fails_closed_when_sidecar_unreachable():
    respx.post("http://opa.invalid/v1/data/common/subject").mock(side_effect=httpx.ConnectError("connection refused"))

    client = AuthzClient("http://opa.invalid")
    subject = await client.identify("admin-token")

    assert subject is None
