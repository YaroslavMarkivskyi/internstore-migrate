package payments

import future.keywords.if
import data.common

default allow := false

# Payments has no browser-facing endpoint — it's called only by
# checkout-workflow's Temporal activities (charge/refund), which present
# an admin-role internal token (see checkout_workflow.auth.mint_internal_token).
# Wires the check_permission() stub that STR-139 left in routers/payments.py.
allow if {
	common.is_admin
}
