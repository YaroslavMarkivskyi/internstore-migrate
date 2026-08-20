from typing import Annotated, Literal

from fastapi import Header, HTTPException, WebSocket, WebSocketException, status
from pydantic import BaseModel


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest", "assistant"]


# Identity extraction, not verification: chat-gate (nginx `auth_request`)
# + chat-verify (services/internal-gate) + chat-opa (policies/chat.rego)
# already verified the caller's internal token and forwarded X-User-Id/
# X-User-Role as trusted headers -- this app is unreachable on any other
# path (HOST=127.0.0.1, see docker-compose.yml). Room-ownership checks
# (routers/mode.py's _room_owner_matches, routers/attachments.py's
# _authorize_room_access, ws/room.py's own copy) still need to know *who*
# the caller is, just don't verify that identity themselves anymore.
def get_internal_claims(
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
) -> InternalClaims:
    if x_user_id is None or x_user_role is None or x_user_role not in ("customer", "admin", "guest", "assistant"):
        # Should be unreachable in practice: every route that depends on
        # this always sits behind chat-gate's @gated location, which
        # never forwards a request without both headers set (auth_request
        # already 401'd it otherwise). Fails closed instead of trusting a
        # malformed identity if that invariant is ever broken.
        raise HTTPException(status_code=401, detail="Missing internal identity")
    return InternalClaims(sub=x_user_id, role=x_user_role)


# Same identity-extraction reasoning as get_internal_claims above, just
# reading the headers off the WebSocket handshake instead of FastAPI's
# Header() DI, which only works for regular routes -- the handshake goes
# through the same chat-gate auth_request as any REST call (see
# nginx/internal-gate/chat.conf), so X-User-Id/X-User-Role are already
# set on it by the time this app sees it.
async def get_internal_claims_ws(websocket: WebSocket) -> InternalClaims:
    x_user_id = websocket.headers.get("x-user-id")
    x_user_role = websocket.headers.get("x-user-role")
    if x_user_id is None or x_user_role is None or x_user_role not in ("customer", "admin", "guest", "assistant"):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing internal identity")
    return InternalClaims(sub=x_user_id, role=x_user_role)
