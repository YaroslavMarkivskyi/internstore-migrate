import httpx


class MCPGatewayClient:
    """Talks to the MCP Gateway's /mcp/* routes. Every call forwards the
    caller's own internal-token (see react_loop.py) rather than minting one
    — the whole point of STR-146's trust-model change is that ownership on
    the customer-scoped tools (get_cart/add_to_cart/remove_from_cart)
    resolves against the real customer, not against AI Assistant's own
    identity."""

    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"X-Internal-Token": token}

    async def list_tools(self, token: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self._base_url}/mcp/tools", headers=self._headers(token))
        resp.raise_for_status()
        return resp.json()["tools"]

    async def call_tool(self, token: str, name: str, arguments: dict) -> object:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/mcp/tools/call",
                json={"name": name, "arguments": arguments},
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()["result"]
