import httpx
from fastapi import Request


class CatalogUnavailableError(Exception):
    """Raised when Catalog times out, refuses connection, or 5xxs."""


class CatalogClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def get_product_price(self, product_id: str) -> float:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(f"{self._base_url}/products/{product_id}")
        except (httpx.TimeoutException, httpx.ConnectError, httpx.TransportError) as exc:
            raise CatalogUnavailableError("catalog unreachable") from exc

        if resp.status_code >= 500:
            raise CatalogUnavailableError(f"catalog returned {resp.status_code}")
        resp.raise_for_status()
        return resp.json()["price"]


async def get_catalog_client(request: Request) -> CatalogClient:
    return request.app.state.catalog_client
