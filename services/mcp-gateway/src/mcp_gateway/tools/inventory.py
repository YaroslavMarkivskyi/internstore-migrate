import httpx


class InventoryToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"X-Internal-Token": token}

    async def check_availability(self, token: str, product_id: str, quantity: int) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/stocks/check-availability",
                json={"items": [{"product_id": product_id, "quantity": quantity}]},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()

    async def get_stock_levels(self, token: str, warehouse_id: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/items/detailed",
                params={"stock_id": warehouse_id},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()

    # No single endpoint returns is_unavailable across every stock (that
    # field only comes back on the per-stock /stocks/{id}/items route, not
    # the cross-stock /items/detailed one) -- list stocks, then fan out to
    # each stock's items and filter. Fine for the admin-use, low-frequency
    # "what's flagged" query this backs.
    async def get_unavailable_items(self, token: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            stocks_resp = await client.get(f"{self._base_url}/stocks", headers=self._headers(token))
            stocks_resp.raise_for_status()
            stocks = stocks_resp.json()

            unavailable: list[dict] = []
            for stock in stocks:
                items_resp = await client.get(
                    f"{self._base_url}/stocks/{stock['id']}/items", headers=self._headers(token)
                )
                items_resp.raise_for_status()
                for item in items_resp.json():
                    if item["is_unavailable"]:
                        unavailable.append({**item, "stock_name": stock["name"]})
        return unavailable
