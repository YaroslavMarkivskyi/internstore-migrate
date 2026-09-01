"""Per-request internal-token plumbing for the ADK agents.

The MCP Gateway wants the *caller's own* `X-Internal-Token` on every tool
call (STR-146 — cart ownership resolves against the real customer, not this
service). That token has a ~60s TTL and can expire mid-run, so it's wrapped
in a `RefreshableToken` that renews itself via auth-backend.

ADK builds the agent + `McpToolset` once at startup, but the token is
per-request. `McpToolset(header_provider=...)` is called per MCP session to
mint headers — so we stash the request's `RefreshableToken` in a ContextVar
(set by the endpoint, which awaits the whole `Runner.run_async` in the same
task) and the header provider reads it back.
"""

import contextvars
from collections.abc import Awaitable, Callable

from google.adk.agents.readonly_context import ReadonlyContext

from ai_assistant.auth_backend_client import AuthBackendClient
from ai_assistant.token_manager import RefreshableToken

_current_token: contextvars.ContextVar[RefreshableToken] = contextvars.ContextVar("internal_token")


def set_request_token(token: str) -> contextvars.Token:
    """Called by the agent endpoint before driving the Runner. Returns the
    reset handle so the caller can restore the previous value."""
    return _current_token.set(RefreshableToken(token))


def reset_request_token(handle: contextvars.Token) -> None:
    _current_token.reset(handle)


HeaderProvider = Callable[[ReadonlyContext], Awaitable[dict[str, str]]]


def make_header_provider(auth_backend_client: AuthBackendClient, refresh_margin_seconds: int) -> HeaderProvider:
    async def header_provider(_ctx: ReadonlyContext) -> dict[str, str]:
        token = _current_token.get()
        await token.ensure_fresh(auth_backend_client, refresh_margin_seconds)
        return {"X-Internal-Token": token.value}

    return header_provider
