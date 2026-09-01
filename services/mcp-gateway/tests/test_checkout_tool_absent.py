"""STR-146: checkout/charge_payment/finalize-purchase must never be callable
by an agent through this Gateway — cart-building only. The control is
structural (no registry entry to route to), not a prompt instruction, so an
adversarial prompt that talks an LLM into *attempting* the call still fails
the same way a typo would."""

from mcp_gateway.schema import TOOL_SPECS_BY_NAME
from tests.conftest import mcp_session, mint_internal_token

FORBIDDEN_NAMES = ["checkout", "charge_payment", "place_order", "confirm_purchase", "pay"]


def test_no_checkout_or_payment_tool_in_the_published_spec():
    for name in FORBIDDEN_NAMES:
        assert name not in TOOL_SPECS_BY_NAME


def test_list_tools_response_never_advertises_a_checkout_tool():
    names = {spec["name"] for spec in TOOL_SPECS_BY_NAME.values()}
    assert not any("checkout" in name or "payment" in name or "charge" in name for name in names)


async def test_calling_a_hallucinated_checkout_tool_is_an_error_not_a_refusal(app):
    # Even if an LLM emits a tool call named "checkout", the Gateway has
    # nothing registered under that name — it comes back as a plain tool
    # error, the same failure mode as a client typo. No LLM "refusal" step
    # to bypass.
    async with mcp_session(app, mint_internal_token("mcp-gateway", "admin")) as session:
        result = await session.call_tool("checkout", {})
    assert result.isError is True
    assert "checkout" in result.content[0].text


async def test_calling_charge_payment_is_an_error(app):
    async with mcp_session(app, mint_internal_token("mcp-gateway", "admin")) as session:
        result = await session.call_tool("charge_payment", {"amount": 34.50})
    assert result.isError is True
