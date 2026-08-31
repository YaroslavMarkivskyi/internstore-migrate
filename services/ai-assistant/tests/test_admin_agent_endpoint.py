"""POST /agent/admin — the internal ops assistant. Admin-only (fail-closed
second check), read-only tools, streams its reply to Chat exactly like the
shopping agent."""

from unittest.mock import AsyncMock

from tests.conftest import mint_internal_token
from tests.gemini_fakes import chunk, set_stream

OPS_ROOM = "room_ops_admin-1"


def _admin_token() -> str:
    return mint_internal_token(sub="admin-1", role="admin")


async def test_admin_message_runs_the_ops_agent_and_streams_the_reply(client, app):
    app.state.mcp_client.list_tools = AsyncMock(return_value=[])
    set_stream(app.state.genai_client, chunk("No orders are stuck in pending."))

    resp = await client.post(
        "/agent/admin",
        json={"room_id": OPS_ROOM, "sender_id": "admin-1", "message": "anything stuck?"},
        headers={"X-Internal-Token": _admin_token()},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    done = app.state.chat_client.stream_done.await_args
    assert done.args[0] == OPS_ROOM
    assert done.args[2] == "No orders are stuck in pending."


async def test_customer_token_is_rejected_by_the_ops_agent(client, app, customer_token):
    resp = await client.post(
        "/agent/admin",
        json={"room_id": OPS_ROOM, "sender_id": "customer-1", "message": "anything stuck?"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 403
    app.state.genai_client.aio.models.generate_content_stream.assert_not_awaited()


async def test_ops_agent_rejects_a_token_sub_that_does_not_match_sender_id(client, app):
    resp = await client.post(
        "/agent/admin",
        json={"room_id": OPS_ROOM, "sender_id": "someone-else", "message": "hi"},
        headers={"X-Internal-Token": _admin_token()},
    )

    assert resp.status_code == 401
