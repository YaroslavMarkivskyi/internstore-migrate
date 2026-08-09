package checkout

import future.keywords.if
import data.common

default allow := false

# checkout-workflow's Temporal activities present an admin-role internal
# token when calling back into Orders' /internal/checkout-workflow/*
# endpoints (create_order, update_order_status) — same identity as every
# other service's mint_internal_token pattern.
allow if {
	common.is_admin
}

# The actual checkout call (POST /checkout/v2, and polling its status via
# GET /checkout/v2/{workflow_id}) is customer/guest-facing — a signed-in
# customer or an anonymous guest may always check out their own cart. Wires
# the check_permission() stub STR-139 left in routers/checkout_v2.py.
allow if {
	input.action == "checkout"
	input.subject.role in ["customer", "guest"]
}
