package orders

import future.keywords.if
import data.common

default allow := false

# Exported so orders-verify (internal-gate) can tell "no valid token"
# (subject undefined -> 401) apart from "valid token, insufficient role"
# (subject present, allow false -> 403) in one call -- see
# services/internal-gate and nginx/internal-gate/orders.conf.
subject := common.subject

# Route-level gate tiers -- queried by orders-verify/internal-gate via
# input.token + input.required_role (no input.action/input.resource at
# all -- see nginx/internal-gate/orders.conf's $orders_auth_tier map).
# Admin can always do everything, so it needs no explicit required_role
# check of its own.
allow if {
	common.is_admin
}

# GET /admin also accepts the AI Assistant's "assistant" role -- see
# routers/orders_admin.py's list_orders_admin docstring.
allow if {
	input.required_role == "admin_or_assistant"
	subject.role == "assistant"
}

# Every other gated route (cart, checkout, checkout/v2, /orders list/
# single, payment-intent, pay) just needs *some* authenticated identity --
# customer/guest/assistant/admin alike. GET /orders/{id}'s own
# resource-ownership check (order.owner_id == caller's sub) is a plain
# comparison of two values orders' own code already has in hand (the
# forwarded X-User-Id and the row it just SELECTed) -- no OPA round-trip
# needed for that, see routers/orders.py's get_order.
allow if {
	input.required_role == "any"
	subject
}
