"""Fixtures for the shopping-agent evals.

Every test here is `@pytest.mark.eval` and skipped unless GCP_PROJECT is set
(the default `uv run pytest` also filters `-m 'not eval'` — see pyproject).
Running them calls a real Gemini model and costs a few cents.
"""

import os
from pathlib import Path

import jwt
import pytest
from google import genai

from ai_assistant.token_manager import RefreshableToken

from evals.harness import FakeMCPGatewayClient

_INTERNAL_SECRET = "eval-secret"
_CUSTOMER_SUB = "eval-customer-0000"


_EVALS_DIR = Path(__file__).parent


def pytest_collection_modifyitems(config, items):
    # This conftest's hooks run session-wide; only auto-mark items that
    # actually live under evals/.
    for item in items:
        try:
            item.path.relative_to(_EVALS_DIR)
        except ValueError:
            continue
        item.add_marker(pytest.mark.eval)


@pytest.fixture(scope="session")
def gcp_project() -> str:
    project = os.environ.get("GCP_PROJECT")
    if not project:
        pytest.skip("GCP_PROJECT not set — shopping-agent evals need a real Vertex project + ADC")
    return project


@pytest.fixture
def genai_client(gcp_project: str) -> genai.Client:
    # Function-scoped, not session: genai.Client().aio holds an async HTTP
    # client bound to the running event loop, and pytest-asyncio gives each
    # test its own loop — a shared client breaks with "Event loop is closed"
    # on the second test. Construction is offline and cheap.
    return genai.Client(
        enterprise=True,
        project=gcp_project,
        location=os.environ.get("GCP_LOCATION", "global"),
    )


@pytest.fixture(scope="session")
def chat_model() -> str:
    return os.environ.get("CHAT_MODEL", "gemini-2.5-flash")


@pytest.fixture
def mcp() -> FakeMCPGatewayClient:
    return FakeMCPGatewayClient()


@pytest.fixture
def token() -> RefreshableToken:
    # No `exp` claim → RefreshableToken never tries to refresh, so the
    # auth-backend client is never touched.
    raw = jwt.encode(
        {"sub": _CUSTOMER_SUB, "role": "customer", "iss": "internstore-gateway"},
        _INTERNAL_SECRET,
        algorithm="HS256",
    )
    return RefreshableToken(raw)


@pytest.fixture
def run_agent(genai_client, chat_model, mcp, token):
    """Returns an async callable: run_agent(message, viewing_product_id=None,
    history=None) -> (reply, mcp). Reuses the same fake gateway across turns
    within one test so the cart persists."""
    from unittest.mock import AsyncMock

    from google.genai import errors as genai_errors

    from ai_assistant.react_loop import run_shopping_agent

    async def _run(message: str, *, viewing_product_id: str | None = None, history=None) -> tuple[str, FakeMCPGatewayClient]:
        try:
            reply = await run_shopping_agent(
                genai_client=genai_client,
                mcp_client=mcp,
                auth_backend_client=AsyncMock(),
                chat_model=chat_model,
                message=message,
                viewing_product_id=viewing_product_id,
                token=token,
                history=history,
            )
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) == 429:
                pytest.skip("Vertex quota exhausted (429) — rerun later or raise the quota")
            raise
        return reply, mcp

    return _run
