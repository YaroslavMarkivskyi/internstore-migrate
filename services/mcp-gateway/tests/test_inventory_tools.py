import httpx
import respx

from mcp_gateway.tools.inventory import InventoryToolsClient

BASE_URL = "http://inventory.invalid"


def _client() -> InventoryToolsClient:
    return InventoryToolsClient(BASE_URL, timeout_seconds=5.0)


@respx.mock
async def test_check_availability_sends_single_item_request():
    route = respx.post(f"{BASE_URL}/stocks/check-availability").mock(
        return_value=httpx.Response(
            200,
            json={
                "sufficient": True,
                "items": [{"product_id": "prod-1", "requested": 2, "available": 5, "sufficient": True}],
            },
        )
    )

    result = await _client().check_availability("caller-token", "prod-1", 2)

    assert route.called
    sent_body = route.calls.last.request.content
    assert b"prod-1" in sent_body
    assert result["sufficient"] is True


@respx.mock
async def test_get_stock_levels_passes_stock_id_param():
    route = respx.get(f"{BASE_URL}/items/detailed", params={"stock_id": "stock-1"}).mock(
        return_value=httpx.Response(200, json=[{"product_id": "prod-1", "quantity": 10}])
    )

    result = await _client().get_stock_levels("caller-token", "stock-1")

    assert route.called
    assert result == [{"product_id": "prod-1", "quantity": 10}]


@respx.mock
async def test_get_unavailable_items_fans_out_across_stocks_and_filters():
    respx.get(f"{BASE_URL}/stocks").mock(
        return_value=httpx.Response(
            200, json=[{"id": "stock-1", "name": "Freezer A"}, {"id": "stock-2", "name": "Freezer B"}]
        )
    )
    respx.get(f"{BASE_URL}/stocks/stock-1/items").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "item-1", "product_id": "prod-1", "quantity": 3, "is_unavailable": True},
                {"id": "item-2", "product_id": "prod-2", "quantity": 5, "is_unavailable": False},
            ],
        )
    )
    respx.get(f"{BASE_URL}/stocks/stock-2/items").mock(return_value=httpx.Response(200, json=[]))

    result = await _client().get_unavailable_items("caller-token")

    assert len(result) == 1
    assert result[0]["product_id"] == "prod-1"
    assert result[0]["stock_name"] == "Freezer A"
