import httpx

from mcp_gateway.auth import mint_internal_token


class StoreNotFoundError(Exception):
    pass


class TelemetryToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._secret = internal_token_secret

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": mint_internal_token(self._secret)}

    async def _list_stores(self, client: httpx.AsyncClient) -> list[dict]:
        resp = await client.get(f"{self._base_url}/stores", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # No GET /stores/{id} exists (only PATCH/readings/incidents sub-routes —
    # see telemetry/routers/stores.py), so this pulls the list and filters,
    # same trade-off as Orders' get_pending_orders.
    async def get_store_temperature(self, store_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            stores = await self._list_stores(client)
        for store in stores:
            if store["id"] == store_id:
                return store
        raise StoreNotFoundError(store_id)

    async def get_temperature_readings(self, store_id: str, period: str = "week") -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/stores/{store_id}/readings",
                params={"period": period},
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    # "Active" mirrors stores.py's own has_open_violation flag (an incident
    # started within the last hour) -- fan out to each flagged store's
    # incident list rather than re-deriving that window here.
    async def get_active_incidents(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            stores = await self._list_stores(client)
            incidents: list[dict] = []
            for store in stores:
                if not store["has_open_violation"]:
                    continue
                resp = await client.get(
                    f"{self._base_url}/stores/{store['id']}/incidents", headers=self._headers()
                )
                resp.raise_for_status()
                incidents.extend({**incident, "store_name": store["name"]} for incident in resp.json())
        return incidents
