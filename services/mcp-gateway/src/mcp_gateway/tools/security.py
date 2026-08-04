import httpx

from mcp_gateway.auth import mint_internal_token


class SecurityToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._secret = internal_token_secret

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": mint_internal_token(self._secret)}

    async def get_visit_log(self, warehouse_id: str, date_from: str, date_to: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/visit-log",
                params={"warehouse_id": warehouse_id, "date_from": date_from, "date_to": date_to},
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()

    async def get_active_users(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/users",
                params={"is_active": "true"},
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()
