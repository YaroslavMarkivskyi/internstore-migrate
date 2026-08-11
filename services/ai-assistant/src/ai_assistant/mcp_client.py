import httpx


def _raise_with_detail(resp: httpx.Response) -> None:
    """Same intent as resp.raise_for_status(), but the error message the
    ReAct loop feeds back to the model (react_loop.py: `json.dumps({"error":
    str(exc)})`) includes the Gateway's actual `detail` — e.g. "product_id
    must be a UUID from a previous search_products or get_cart result, got
    'Aged Dutch Gouda'" — instead of raise_for_status()'s generic "Client
    error '422 Unprocessable Entity' for url '...'". Found live: the
    original generic message gave the model nothing to act on, so a bad
    tool call just failed outright instead of the model correcting itself
    within the same loop."""
    if resp.is_success:
        return
    try:
        detail = resp.json().get("detail")
    except ValueError:
        detail = None
    message = f"{resp.status_code} {resp.reason_phrase}: {detail}" if detail else f"{resp.status_code} {resp.reason_phrase}"
    raise httpx.HTTPStatusError(message, request=resp.request, response=resp)


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
        _raise_with_detail(resp)
        return resp.json()["result"]
