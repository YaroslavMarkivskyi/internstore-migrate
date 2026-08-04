import httpx

from ai_assistant.auth import mint_internal_token


class OrdersClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._secret = internal_token_secret

    async def get_recent_orders(self, customer_id: str, limit: int) -> list[dict]:
        token = mint_internal_token(self._secret)
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/orders/admin",
                params={"owner_id": customer_id},
                headers={"X-Internal-Token": token},
            )
        resp.raise_for_status()
        return resp.json()[:limit]
