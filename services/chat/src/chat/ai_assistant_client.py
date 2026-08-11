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

    async def notify_shopping_agent(self, *, room_id: str, sender_id: str, message: str, token: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/agent/shopping",
                    json={"room_id": room_id, "sender_id": sender_id, "message": message},
                    headers={"X-Internal-Token": token},
                )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Best-effort: a failed call here shouldn't take down the
            # customer's own WS message send, which has already succeeded
            # by the time this runs (see ws/room.py) — same trade-off as
            # notification delivery elsewhere in this service.
            logger.warning("Shopping agent call failed for room %s: %s", room_id, exc)
