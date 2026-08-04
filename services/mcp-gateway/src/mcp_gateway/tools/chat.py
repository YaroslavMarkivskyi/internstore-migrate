import httpx

from mcp_gateway.auth import mint_internal_token


class ChatToolsClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._secret = internal_token_secret

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": mint_internal_token(self._secret)}

    async def get_room_summary(self, room_id: str, limit: int = 20) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/rooms/{room_id}/messages",
                params={"limit": limit},
                headers=self._headers(),
            )
        resp.raise_for_status()
        return resp.json()["messages"]

    async def list_active_rooms(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/rooms", headers=self._headers())
        resp.raise_for_status()
        return [room for room in resp.json()["rooms"] if room["unread_count"] > 0]
