import logging

import httpx

logger = logging.getLogger(__name__)


class AIAssistantClient:
    """STR-146: notifies AI Assistant's shopping ReAct loop synchronously,
    forwarding the calling customer's own internal-token unchanged (see
    services/ai-assistant/src/ai_assistant/main.py's POST /agent/shopping) —
    this is the start of the Chat -> Agent Runtime -> MCP Gateway ->
    Orders/Catalog token-propagation chain the ticket calls for. Unlike the
    chat-events Kafka topic (which has no token to carry), this is a direct
    call specifically so a real customer identity reaches the shopping
    agent's tool calls."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def notify_shopping_agent(
        self,
        *,
        room_id: str,
        sender_id: str,
        message: str,
        token: str,
        viewing_product_id: str | None = None,
        viewing_category_id: str | None = None,
    ) -> None:
        body: dict[str, str] = {"room_id": room_id, "sender_id": sender_id, "message": message}
        if viewing_product_id:
            body["viewing_product_id"] = viewing_product_id
        if viewing_category_id:
            body["viewing_category_id"] = viewing_category_id
        await self._post_agent("/agent/shopping", body, token, room_id, "Shopping agent")

    async def notify_admin_agent(self, *, room_id: str, sender_id: str, message: str, token: str) -> None:
        """Ops assistant — see ai-assistant's POST /agent/admin. Same
        forward-the-caller's-token, best-effort contract as
        notify_shopping_agent."""
        body = {"room_id": room_id, "sender_id": sender_id, "message": message}
        await self._post_agent("/agent/admin", body, token, room_id, "Ops assistant")

    async def _post_agent(self, path: str, body: dict, token: str, room_id: str, label: str) -> None:
        # Best-effort: a failed call here must not take down the caller's
        # own WS message send, which has already succeeded by the time this
        # runs (see ws/room.py) — same trade-off as notification delivery
        # elsewhere in this service.
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}{path}", json=body, headers={"X-Internal-Token": token}
                )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("%s call failed for room %s: %s", label, room_id, exc)
