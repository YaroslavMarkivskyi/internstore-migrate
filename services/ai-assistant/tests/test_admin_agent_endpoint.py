"""POST /agent/admin — the internal ops assistant. Admin-only (fail-closed
second check), read-only tools, streams its reply to Chat exactly like the
shopping agent."""

from tests.adk_fakes import fake_agent_stream
from tests.conftest import mint_internal_token

OPS_ROOM = "room_ops_admin-1"


def _admin_token() -> str:
    return mint_internal_token(sub="admin-1", role="admin")


async def test_admin_message_runs_the_ops_agent_and_streams_the_reply(client, app, monkeypatch):
    fake = fake_agent_stream("No orders are stuck in pending.")
    monkeypatch.setattr("ai_assistant.main.run_agent_stream", fake)

    resp = await client.post(
        "/agent/admin",
        json={"room_id": OPS_ROOM, "sender_id": "admin-1", "message": "anything stuck?"},
        headers={"X-Internal-Token": _admin_token()},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert fake.calls[0]["author"] == "ops_assistant"
    done = app.state.chat_client.stream_done.await_args
    assert done.args[0] == OPS_ROOM
    assert done.args[2] == "No orders are stuck in pending."


async def test_customer_token_is_rejected_by_the_ops_agent(client, app, customer_token, monkeypatch):
    fake = fake_agent_stream("should not run")
    monkeypatch.setattr("ai_assistant.main.run_agent_stream", fake)

    resp = await client.post(
        "/agent/admin",
        json={"room_id": OPS_ROOM, "sender_id": "customer-1", "message": "anything stuck?"},
        headers={"X-Internal-Token": customer_token},
    )

    assert resp.status_code == 403
    assert fake.calls == []


async def test_ops_agent_rejects_a_token_sub_that_does_not_match_sender_id(client, app):
    resp = await client.post(
        "/agent/admin",
        json={"room_id": OPS_ROOM, "sender_id": "someone-else", "message": "hi"},
        headers={"X-Internal-Token": _admin_token()},
    )

    assert resp.status_code == 401
