import asyncio
import json

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from chat.ws_manager import WebSocketManager

CHANNEL_PREFIX = "chat:"


def channel_for(room_id: str) -> str:
    return f"{CHANNEL_PREFIX}{room_id}"


class PubSubRouter:
    """Cross-instance fanout for Approach 1: this instance never delivers a
    received WS message directly to its own local clients — it always
    PUBLISHes to Redis first, then delivers (including back to the sender)
    only when that same message comes back through this subscription. Each
    instance subscribes only to the Redis channels for rooms where it
    currently has at least one local connection (see ws/room.py, which
    calls subscribe()/unsubscribe() based on WebSocketManager's
    first-connection/last-disconnection signal).

    Each active room gets its own dedicated PubSub connection + listener
    task, created on subscribe() and torn down (cancelled + closed, not
    reused) on unsubscribe() — rather than repeatedly
    subscribing/unsubscribing channels on one long-lived shared PubSub
    connection. redis-py's PubSub.listen() runs an internal
    `while self.subscribed:` loop that returns the instant a shared
    connection's last channel is unsubscribed, and re-subscribing that same
    connection afterward is a state transition most PubSub client
    implementations (including fakeredis, which this test suite runs
    against) don't reliably support — a fresh connection per room sidesteps
    that whole class of problem, at the cost of one extra Redis connection
    per concurrently-active room, which is a fine trade for a chat service
    where "concurrently active rooms on one instance" is nowhere near
    Redis's connection limits."""

    def __init__(self, redis: Redis, ws_manager: WebSocketManager) -> None:
        self._redis = redis
        self._ws_manager = ws_manager
        self._rooms: dict[str, tuple[PubSub, asyncio.Task]] = {}

    async def subscribe(self, room_id: str) -> None:
        if room_id in self._rooms:
            return
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel_for(room_id))
        task = asyncio.create_task(self._run_listener(room_id, pubsub))
        self._rooms[room_id] = (pubsub, task)

    async def unsubscribe(self, room_id: str) -> None:
        entry = self._rooms.pop(room_id, None)
        if entry is None:
            return
        pubsub, task = entry
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await pubsub.aclose()

    async def publish(self, room_id: str, payload: dict) -> None:
        await self._redis.publish(channel_for(room_id), json.dumps(payload))

    async def _run_listener(self, room_id: str, pubsub: PubSub) -> None:
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                payload = json.loads(message["data"])
                await self._ws_manager.broadcast_local(room_id, payload)
        except asyncio.CancelledError:
            raise

    async def close(self) -> None:
        for room_id in list(self._rooms):
            await self.unsubscribe(room_id)
