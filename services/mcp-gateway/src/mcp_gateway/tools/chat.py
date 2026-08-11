import httpx


class ChatToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"X-Internal-Token": token}

    async def get_room_summary(self, token: str, room_id: str, limit: int = 20) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/rooms/{room_id}/messages",
                params={"limit": limit},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()["messages"]

    async def list_active_rooms(self, token: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/rooms", headers=self._headers(token))
        resp.raise_for_status()
        return [room for room in resp.json()["rooms"] if room["unread_count"] > 0]
