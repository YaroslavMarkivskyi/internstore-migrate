package inventory

import future.keywords.if
import data.common

default allow := false

# Exported so inventory-verify (internal-gate) can tell "no valid token"
# (subject undefined -> 401) apart from "valid token, insufficient role"
# (subject present, allow false -> 403) in one call -- see
# services/internal-gate and nginx/internal-gate/inventory.conf.
subject := common.subject

# nginx/internal-gate/inventory.conf sets X-Required-Role to "any" for the
# three routes that only ever checked get_internal_claims with no
# require_admin/require_authz on top -- POST /stocks/check-availability,
# /stocks/reserve, /stocks/release (see routers/stocks.py's git history).
# Every other gated route defaults to "admin", same as require_admin/
# require_authz's previous behavior on stock/stock_item mutations and the
# history/as-of read endpoints.
required_role := object.get(input, "required_role", "admin")

allow if {
	required_role == "admin"
	common.is_admin
}

allow if {
	required_role == "any"
	subject
}
