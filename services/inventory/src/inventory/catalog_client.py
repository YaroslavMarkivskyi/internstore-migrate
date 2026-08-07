import logging

import httpx
from fastapi import Request

from inventory.auth import mint_internal_token

logger = logging.getLogger(__name__)


class CatalogClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._internal_token_secret = internal_token_secret

    async def unpublish_product(self, product_id: str) -> None:
        # Best-effort: a product going invisible to customers once it's out
        # of stock everywhere is a UX nicety on top of whatever inventory
        # operation (item delete, quantity edit, an order consuming the
        # last unit) triggered this -- Catalog being briefly unreachable
        # shouldn't fail that otherwise-valid operation, so failures here
        # are logged and swallowed rather than propagated to the caller.
        token = mint_internal_token(self._internal_token_secret)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.patch(
                    f"{self._base_url}/products/{product_id}",
                    json={"is_published": False},
                    headers={"X-Internal-Token": token},
                )
            resp.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Failed to unpublish out-of-stock product %s", product_id, exc_info=True)


async def get_catalog_client(request: Request) -> CatalogClient:
    return request.app.state.catalog_client
