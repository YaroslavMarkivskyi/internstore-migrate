"""ADK agent definitions — the shopping assistant and the internal ops
assistant, both `LlmAgent`s whose tools are the MCP Gateway's, reached over
the real MCP protocol via ADK's `McpToolset`."""

from google.adk.agents import LlmAgent
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

from ai_assistant.adk.prompts import (
    ADMIN_INSTRUCTION,
    ADMIN_TOOL_NAMES,
    SHOPPING_INSTRUCTION,
    SHOPPING_TOOL_NAMES,
)
from ai_assistant.adk.token_context import HeaderProvider

SHOPPING_AGENT_NAME = "shopping_assistant"
OPS_AGENT_NAME = "ops_assistant"


def _gateway_toolset(
    *, mcp_url: str, tool_filter: tuple[str, ...], header_provider: HeaderProvider
) -> McpToolset:
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=mcp_url.rstrip("/") + "/mcp/stream"),
        tool_filter=list(tool_filter),
        header_provider=header_provider,
        # The gateway's tool set never changes at runtime; cache the list so a
        # rotating token (each mints a fresh MCP session) doesn't re-list.
        tool_list_cache_ttl_seconds=300,
    )


def build_shopping_agent(
    *, model: str, mcp_gateway_url: str, header_provider: HeaderProvider, extra_tools: tuple = ()
) -> LlmAgent:
    return LlmAgent(
        name=SHOPPING_AGENT_NAME,
        model=model,
        instruction=SHOPPING_INSTRUCTION,
        tools=[
            _gateway_toolset(
                mcp_url=mcp_gateway_url, tool_filter=SHOPPING_TOOL_NAMES, header_provider=header_provider
            ),
            *extra_tools,
        ],
    )


def build_ops_agent(
    *, model: str, mcp_gateway_url: str, header_provider: HeaderProvider, extra_tools: tuple = ()
) -> LlmAgent:
    return LlmAgent(
        name=OPS_AGENT_NAME,
        model=model,
        instruction=ADMIN_INSTRUCTION,
        tools=[
            _gateway_toolset(
                mcp_url=mcp_gateway_url, tool_filter=ADMIN_TOOL_NAMES, header_provider=header_provider
            ),
            *extra_tools,
        ],
    )


async def close_toolsets(agent: LlmAgent) -> None:
    """Close every MCP session the agent's toolsets hold — call on shutdown."""
    for tool in agent.tools:
        if isinstance(tool, BaseToolset):
            await tool.close()
