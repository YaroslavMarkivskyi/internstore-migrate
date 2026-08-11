import httpx
import pytest
import respx

from mcp_gateway.tools.telemetry import StoreNotFoundError, TelemetryToolsClient

BASE_URL = "http://telemetry.invalid"


def _client() -> TelemetryToolsClient:
    return TelemetryToolsClient(BASE_URL, timeout_seconds=5.0)


@respx.mock
async def test_get_store_temperature_filters_from_store_list():
    respx.get(f"{BASE_URL}/stores").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "store-1", "name": "Downtown", "current_temperature": 4.1, "has_open_violation": False},
                {"id": "store-2", "name": "Uptown", "current_temperature": 9.5, "has_open_violation": True},
            ],
        )
    )

    result = await _client().get_store_temperature("caller-token", "store-2")

    assert result["current_temperature"] == 9.5
    assert result["has_open_violation"] is True


@respx.mock
async def test_get_store_temperature_unknown_store_raises():
    respx.get(f"{BASE_URL}/stores").mock(return_value=httpx.Response(200, json=[]))

    with pytest.raises(StoreNotFoundError):
        await _client().get_store_temperature("caller-token", "missing-store")


@respx.mock
async def test_get_active_incidents_only_fans_out_to_violating_stores():
    respx.get(f"{BASE_URL}/stores").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "store-1", "name": "Downtown", "has_open_violation": False},
                {"id": "store-2", "name": "Uptown", "has_open_violation": True},
            ],
        )
    )
    incidents_route = respx.get(f"{BASE_URL}/stores/store-2/incidents").mock(
        return_value=httpx.Response(200, json=[{"id": "incident-1", "temperature_at_outbreak": 9.5}])
    )

    result = await _client().get_active_incidents("caller-token")

    assert incidents_route.called
    assert len(result) == 1
    assert result[0]["store_name"] == "Uptown"
