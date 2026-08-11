import httpx


class SecurityToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"X-Internal-Token": token}

    async def get_visit_log(self, token: str, warehouse_id: str, date_from: str, date_to: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/visit-log",
                params={"warehouse_id": warehouse_id, "date_from": date_from, "date_to": date_to},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()

    async def get_active_users(self, token: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/users",
                params={"is_active": "true"},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()
