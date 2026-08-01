import uuid

import httpx
import pytest
import respx

from orders.inventory_client import InventoryClient, InventoryUnavailableError


@respx.mock
async def test_check_availability_sends_expected_request_shape():
    product_id = str(uuid.uuid4())
    route = respx.post("http://inventory.invalid/stocks/check-availability").mock(
        return_value=httpx.Response(
            200,
            json={"sufficient": True, "items": [{"product_id": product_id, "requested": 1, "available": 1, "sufficient": True}]},
        )
    )

    client = InventoryClient("http://inventory.invalid", timeout_seconds=5.0)
    result = await client.check_availability([{"product_id": product_id, "quantity": 1}], "some-internal-token")

    assert route.called
    request = route.calls.last.request
    assert request.method == "POST"
    assert request.headers["x-internal-token"] == "some-internal-token"
    assert product_id.encode() in request.content
    assert result["sufficient"] is True


@respx.mock
async def test_check_availability_5xx_raises_unavailable():
    respx.post("http://inventory.invalid/stocks/check-availability").mock(return_value=httpx.Response(503))

    client = InventoryClient("http://inventory.invalid", timeout_seconds=5.0)
    with pytest.raises(InventoryUnavailableError):
        await client.check_availability([{"product_id": str(uuid.uuid4()), "quantity": 1}], "token")


@respx.mock
async def test_check_availability_timeout_raises_unavailable():
    respx.post("http://inventory.invalid/stocks/check-availability").mock(side_effect=httpx.TimeoutException("timed out"))

    client = InventoryClient("http://inventory.invalid", timeout_seconds=5.0)
    with pytest.raises(InventoryUnavailableError):
        await client.check_availability([{"product_id": str(uuid.uuid4()), "quantity": 1}], "token")
