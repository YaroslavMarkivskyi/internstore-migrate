import httpx
from fastapi import Request


class InventoryUnavailableError(Exception):
    """Raised when Inventory times out, refuses connection, or 5xxs."""


class InventoryClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def get_total_quantity(self, product_id: str, internal_token: str) -> int:
        # Forwards the caller's own token (the request that's trying to
        # publish this product is already admin-authenticated -- see
        # update_product) rather than minting a new one, mirroring how
        # Inventory's own outbound calls to Catalog mint their own (that
        # side has no request to forward from, since it's often
        # Kafka-triggered; this side always has one).
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/items",
                    params={"product_id": product_id},
                    headers={"X-Internal-Token": internal_token},
                )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.TransportError) as exc:
            raise InventoryUnavailableError("inventory unreachable") from exc

        if resp.status_code >= 500:
            raise InventoryUnavailableError(f"inventory returned {resp.status_code}")
        resp.raise_for_status()
        items = resp.json()
        return sum(item["quantity"] for item in items)


async def get_inventory_client(request: Request) -> InventoryClient:
    return request.app.state.inventory_client
