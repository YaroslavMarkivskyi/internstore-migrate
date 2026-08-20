package orders

import future.keywords.if
import data.common

default allow := false

# Exported so orders-verify (internal-gate) can tell "no valid token"
# (subject undefined -> 401) apart from "valid token, insufficient role"
# (subject present, allow false -> 403) in one call -- see
# services/internal-gate and nginx/internal-gate/orders.conf.
subject := common.subject

# --- Route-level gate tiers -- queried by orders-verify/internal-gate via
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
# customer/guest/assistant/admin alike. The resource-ownership rules below
# (GET /orders/{id}, and previously checkout's create_order/
# update_order_status) still apply on top of this for the routes that
# need them, via a *separate* direct call orders' own code makes to this
# same OPA sidecar (see routers/orders.py's get_order) -- this rule only
# covers the coarse "is this caller authenticated at all" gate check.
allow if {
	input.required_role == "any"
	subject
}

# --- Resource-level checks -- called directly by orders' own code
# (routers/orders.py's get_order), since owner_id lives in Orders' own DB
# and is unreachable from the gate. These queries carry input.subject/
# input.action/input.resource, never input.required_role, so they never
# collide with the route-level tiers above.
allow if {
	input.action in ["view", "update"]
	input.resource.type == "order"
	input.subject.role == "customer"
	common.is_resource_owner
}

allow if {
	input.action == "create"
	input.resource.type == "order"
	input.subject.role == "guest"
}
