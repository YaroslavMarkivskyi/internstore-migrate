from datetime import datetime, timedelta, timezone

import httpx

from mcp_gateway.auth import mint_internal_token


class OrdersToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._secret = internal_token_secret

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": mint_internal_token(self._secret)}

    async def get_order_status(self, order_id: str) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/orders/admin/{order_id}", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def list_customer_orders(self, customer_id: str, limit: int = 5) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/orders/admin",
                params={"owner_id": customer_id},
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()[:limit]

    # Orders has no server-side filter for "stuck in Pending" -- this pulls
    # the full admin list and filters client-side, same trade-off as
    # get_unavailable_items in tools/inventory.py. Fine for a thin,
    # low-volume admin tool; would need a real query param on GET
    # /orders/admin if this became a hot path.
    async def get_pending_orders(self, older_than_minutes: int = 60) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/orders/admin", headers=self._headers())
        resp.raise_for_status()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        return [
            order
            for order in resp.json()
            if order["status"] == "pending" and datetime.fromisoformat(order["created_at"]) <= cutoff
        ]
