import httpx
from fastapi import Request


class InventoryUnavailableError(Exception):
    """Raised when Inventory times out, refuses connection, or 5xxs."""


class InventoryClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def check_availability(self, items: list[dict], internal_token: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/stocks/check-availability",
                    json={"items": items},
                    headers={"X-Internal-Token": internal_token},
                )
        except (httpx.TimeoutException, httpx.ConnectError, httpx.TransportError) as exc:
            raise InventoryUnavailableError("inventory unreachable") from exc

        if resp.status_code >= 500:
            raise InventoryUnavailableError(f"inventory returned {resp.status_code}")
        resp.raise_for_status()
        return resp.json()


async def get_inventory_client(request: Request) -> InventoryClient:
    return request.app.state.inventory_client
