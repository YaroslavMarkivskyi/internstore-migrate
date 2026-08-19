import httpx

from ai_assistant.auth import mint_internal_token


class ChatClient:
    def __init__(self, base_url: str, timeout_seconds: float, internal_token_secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._secret = internal_token_secret

    def _headers(self) -> dict[str, str]:
        return {"X-Internal-Token": mint_internal_token(self._secret)}

    async def get_recent_messages(self, room_id: str, limit: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{self._base_url}/rooms/{room_id}/messages",
                params={"limit": limit},
                headers=self._headers(),
            )
        resp.raise_for_status()
        # Chat returns newest-first (see routers/rooms.py's
        # Message.created_at.desc()) — reverse to oldest-first for the
        # model's conversation contents, which reads top-to-bottom
        # chronologically (context.py/react_loop.py).
        return list(reversed(resp.json()["messages"]))

    async def post_message(self, room_id: str, content: str) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/rooms/{room_id}/messages",
                json={"content": content},
                headers=self._headers(),
            )
        resp.raise_for_status()

    async def set_mode(self, room_id: str, mode: str) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.patch(
                f"{self._base_url}/rooms/{room_id}/mode",
                json={"mode": mode},
                headers=self._headers(),
            )
        resp.raise_for_status()
