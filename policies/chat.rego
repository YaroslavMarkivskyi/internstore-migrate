package chat

import future.keywords.if
import data.common

default allow := false

# Exported so chat-verify (internal-gate) can tell "no valid token"
# (subject undefined -> 401) apart from "valid token, insufficient role"
# (subject present, allow false -> 403) in one call -- see
# services/internal-gate and nginx/internal-gate/chat.conf.
subject := common.subject

# Route-level gate tiers -- queried by chat-verify/internal-gate via
# input.token + input.required_role (see nginx/internal-gate/chat.conf's
# $chat_auth_tier map). Room-ownership decisions ("is this my room") are
# NOT here -- they're pure functions of room_id + the caller's own sub
# (see routers/mode.py's _room_owner_matches and ws/room.py's own copy),
# so they stay inline in chat's own code, same as before, just reading
# forwarded X-User-Id/X-User-Role instead of verifying a JWT itself.
#
# Deliberately NOT a blanket "admin can do anything" rule here (unlike
# catalog/security/payments/inventory/orders) -- POST /rooms/{id}/messages
# is assistant-*only* (mirrors require_assistant's previous behavior,
# which rejected admin too), so admin's bypass has to be spelled out per
# tier instead of unconditionally.
allow if {
	input.required_role == "admin"
	common.is_admin
}

# GET /rooms/{id}/messages also accepts "assistant" -- the AI Assistant
# reads recent history to build conversation context (see
# routers/rooms.py's get_messages docstring).
allow if {
	input.required_role == "admin_or_assistant"
	subject.role in ["admin", "assistant"]
}

# POST /rooms/{id}/messages (routers/internal_messages.py) -- the AI
# Assistant's only way to inject a message into a room. Admin does NOT
# get a bypass here, same as the require_assistant dependency it replaces.
allow if {
	input.required_role == "assistant"
	subject.role == "assistant"
}

# Every other gated route (mode, attachments, the /ws/room/{id} handshake)
# just needs *some* authenticated identity -- the room-ownership check
# happens after, inline in the app, once it has X-User-Id/X-User-Role.
allow if {
	input.required_role == "any"
	subject
}
