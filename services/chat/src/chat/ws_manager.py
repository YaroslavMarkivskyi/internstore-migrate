import asyncio
import json

from fastapi import WebSocket


class WebSocketManager:
    """In-memory map of locally-connected sockets per room, for this
    process only. Cross-instance fanout happens through Redis pub/sub
    (see pubsub.py) — this class only ever delivers to sockets held by the
    current process, which is exactly what "local" means in Approach 1
    (publish first, then every instance — including the sender's own —
    delivers to its local connections from the pub/sub callback)."""

    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def add(self, room_id: str, websocket: WebSocket) -> bool:
        """Returns True if this is the first local connection for the room."""
        async with self._lock:
            is_first = room_id not in self._rooms
            self._rooms.setdefault(room_id, set()).add(websocket)
            return is_first

    async def remove(self, room_id: str, websocket: WebSocket) -> bool:
        """Returns True if no local connections remain for the room."""
        async with self._lock:
            sockets = self._rooms.get(room_id)
            if sockets is None:
                return True
            sockets.discard(websocket)
            if not sockets:
                del self._rooms[room_id]
                return True
            return False

    async def broadcast_local(self, room_id: str, payload: dict) -> None:
        async with self._lock:
            sockets = list(self._rooms.get(room_id, ()))
        message = json.dumps(payload)
        for websocket in sockets:
            await websocket.send_text(message)
