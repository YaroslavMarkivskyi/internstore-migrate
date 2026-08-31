import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from chat.auth import InternalClaims, get_internal_claims_ws
from chat.models import Message, Room, RoomMember, SenderType
from chat.object_storage_dep import resolve_attachment_url
from chat.outbox import add_outbox_event

router = APIRouter()
_tracer = trace.get_tracer(__name__)


async def _notify_shopping_agent_traced(client, **kwargs) -> None:
    """STR-158b: roots the shopping-agent trace (STR-158) here — a
    WebSocket message isn't itself an ASGI HTTP request, so
    FastAPIInstrumentor never creates a span for it, and this call runs in
    a fire-and-forget asyncio.create_task with no other active span to
    attach to. This span becomes that root; HTTPXClientInstrumentor
    propagates it into the POST to ai-assistant, and from there into
    ai-assistant's own outbound calls to MCP Gateway and Orders."""
    with _tracer.start_as_current_span("chat.notify_shopping_agent"):
        await client.notify_shopping_agent(**kwargs)


def _room_owner_matches(role: str, room_id: str, sub: str) -> bool:
    return role == "admin" or room_id == f"room_{sub}"


def _valid_uuid_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(uuid.UUID(value))
    except ValueError:
        return None


async def _get_or_create_room(session, room_id: str, claims: InternalClaims) -> Room:
    room = await session.get(Room, room_id)
    if room is not None:
        return room
    room = Room(
        id=room_id,
        customer_id=uuid.UUID(claims.sub) if claims.role == "customer" else None,
        session_id=claims.sub if claims.role == "guest" else None,
    )
    session.add(room)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race with another connection lazily creating the same
        # room — fall back to reading what the winner created.
        await session.rollback()
        room = await session.get(Room, room_id)
    return room


async def _join_as_admin(session, room: Room, admin_id: str) -> None:
    membership = await session.get(RoomMember, (room.id, admin_id))
    if membership is None:
        session.add(RoomMember(room_id=room.id, admin_id=admin_id))
    room.notification_sent_at = None
    await session.commit()


async def _send_history(websocket: WebSocket, session, room_id: str, limit: int) -> None:
    result = await session.execute(
        select(Message).where(Message.room_id == room_id).order_by(Message.created_at.desc()).limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    object_storage_client = websocket.app.state.object_storage_client
    await websocket.send_text(
        json.dumps(
            {
                "type": "history",
                "messages": [
                    {
                        "id": str(message.id),
                        "sender_type": message.sender_type.value,
                        "sender_id": message.sender_id,
                        "content": message.content,
                        "attachment_url": await resolve_attachment_url(object_storage_client, message.attachment_key),
                        "created_at": message.created_at.isoformat(),
                    }
                    for message in messages
                ],
            }
        )
    )


@router.websocket("/ws/room/{room_id}")
async def room_websocket(
    websocket: WebSocket,
    room_id: str,
    claims: Annotated[InternalClaims, Depends(get_internal_claims_ws)],
) -> None:
    if not _room_owner_matches(claims.role, room_id, claims.sub):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    app = websocket.app
    session_factory = app.state.session_factory
    ws_manager = app.state.ws_manager
    pubsub = app.state.pubsub
    redis = app.state.redis
    instance_id = app.state.instance_id
    history_limit = app.state.settings.history_replay_limit
    # Local (this-app-instance-only) reference count of admin connections
    # per (room_id, admin_id), so the cross-instance chat:{room_id}:admins
    # Redis set only gets a SREM when this admin's *last* local connection
    # for that room closes — a second browser tab from the same admin
    # shouldn't flip presence off when the first tab disconnects. Lives on
    # app.state (set in main.py's create_app(), not a module global) so
    # it's scoped per FastAPI app instance, same as everything else this
    # handler reads off app.state — a module global would leak state
    # across independent app instances (e.g. between tests).
    admin_local_refcounts: dict[tuple[str, str], int] = app.state.admin_local_refcounts

    await websocket.accept()

    async with session_factory() as session:
        room = await _get_or_create_room(session, room_id, claims)
        if claims.role == "admin":
            await _join_as_admin(session, room, claims.sub)
        if claims.role != "guest":
            await _send_history(websocket, session, room_id, history_limit)

    is_first_local = await ws_manager.add(room_id, websocket)
    if is_first_local:
        await pubsub.subscribe(room_id)
        await redis.sadd(f"chat:{room_id}:connections", instance_id)

    if claims.role == "admin":
        key = (room_id, claims.sub)
        admin_local_refcounts[key] = admin_local_refcounts.get(key, 0) + 1
        if admin_local_refcounts[key] == 1:
            await redis.sadd(f"chat:{room_id}:admins", claims.sub)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            message_type = data.get("type", "message")
            now = datetime.now(timezone.utc)

            if message_type == "typing":
                await pubsub.publish(room_id, {"type": "typing", "room_id": room_id, "sender_id": claims.sub})
                continue

            content = data.get("content")
            # The product / category page the customer had open when they
            # sent this, if any (see frontend ChatWidget). Only forwarded to
            # the shopping agent when well-formed UUIDs — these end up in the
            # model's prompt, so a client must not be able to put arbitrary
            # prose there.
            viewing_product_id = _valid_uuid_or_none(data.get("viewing_product_id"))
            viewing_category_id = _valid_uuid_or_none(data.get("viewing_category_id"))
            # References an object this same caller already uploaded via
            # POST /rooms/{room_id}/attachments (see routers/attachments.py)
            # -- not a URL. Resolved to a fresh presigned attachment_url
            # below, right before this message is published/persisted-for
            # -read, never stored as a URL itself (see Message.attachment_key's
            # docstring).
            attachment_key = data.get("attachment_key")
            sender_type = SenderType.ADMIN if claims.role == "admin" else SenderType.CUSTOMER

            async with session_factory() as session:
                if claims.role != "guest":
                    session.add(
                        Message(
                            room_id=room_id,
                            sender_type=sender_type,
                            sender_id=claims.sub,
                            content=content,
                            attachment_key=attachment_key,
                            created_at=now,
                        )
                    )

                room = await session.get(Room, room_id)
                room.last_message_at = now
                if claims.role in ("customer", "guest"):
                    admin_present = await redis.scard(f"chat:{room_id}:admins")
                    if admin_present == 0 and room.notification_sent_at is None:
                        add_outbox_event(
                            session,
                            "UnreadMessageReceived",
                            {"room_id": room_id, "sender_name": claims.sub},
                        )
                        room.notification_sent_at = now
                    # Every customer/guest message is announced on
                    # chat-events (not just the offline-admin case above) so
                    # the AI Assistant's consumer has something to trigger
                    # off of regardless of whether an admin happens to be
                    # online — it decides for itself whether to respond
                    # based on chat:{room_id}:mode.
                    add_outbox_event(
                        session,
                        "CustomerMessageSent",
                        # STR-148: sender_role explicitly included — found
                        # live that ai-assistant's consumer was trying to
                        # infer "is this a registered customer" from
                        # whether sender_id merely *looks like* a UUID,
                        # which silently broke the moment guest session
                        # ids (also plain uuid4() — see auth-backend's
                        # GuestSessionStore.create) started being handled
                        # differently from customers (STR-146): every
                        # guest message was misclassified as a customer's,
                        # so guests stopped getting any AI reply at all.
                        {"room_id": room_id, "sender_id": claims.sub, "sender_role": claims.role, "content": content},
                    )
                await session.commit()

            # STR-146: registered customers only — guests get no shopping-
            # agent access (see AIAssistantClient's docstring and
            # ai-assistant's own independent role check). Fired as a
            # background task, not awaited, so a slow/unavailable AI
            # Assistant never delays this customer's own message send; the
            # CustomerMessageSent outbox event above still fires for every
            # customer/guest either way, but ai-assistant's Kafka consumer
            # now ignores registered customers (see chat_events.py) since
            # they're handled here instead, with a real token to forward.
            if claims.role == "customer" and content:
                raw_token = websocket.headers.get("x-internal-token", "")
                notify_kwargs: dict[str, str] = {
                    "room_id": room_id,
                    "sender_id": claims.sub,
                    "message": content,
                    "token": raw_token,
                }
                if viewing_product_id is not None:
                    notify_kwargs["viewing_product_id"] = viewing_product_id
                if viewing_category_id is not None:
                    notify_kwargs["viewing_category_id"] = viewing_category_id
                asyncio.create_task(
                    _notify_shopping_agent_traced(app.state.ai_assistant_client, **notify_kwargs)
                )

            await pubsub.publish(
                room_id,
                {
                    "type": "message",
                    "room_id": room_id,
                    "sender_type": sender_type.value,
                    "sender_id": claims.sub,
                    "content": content,
                    "attachment_url": await resolve_attachment_url(app.state.object_storage_client, attachment_key),
                    "created_at": now.isoformat(),
                },
            )
    except WebSocketDisconnect:
        pass
    finally:
        is_last_local = await ws_manager.remove(room_id, websocket)
        if is_last_local:
            await pubsub.unsubscribe(room_id)
            await redis.srem(f"chat:{room_id}:connections", instance_id)

        if claims.role == "admin":
            key = (room_id, claims.sub)
            admin_local_refcounts[key] = admin_local_refcounts.get(key, 1) - 1
            if admin_local_refcounts[key] <= 0:
                admin_local_refcounts.pop(key, None)
                await redis.srem(f"chat:{room_id}:admins", claims.sub)
