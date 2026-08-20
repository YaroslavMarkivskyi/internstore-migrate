package telemetry

import future.keywords.if
import data.common

default allow := false

# Exported so telemetry-verify (internal-gate) can tell "no valid token"
# (subject undefined -> 401) apart from "valid token, insufficient role"
# (subject present, allow false -> 403) in one call -- see
# services/internal-gate and nginx/internal-gate/telemetry.conf.
subject := common.subject

# Every gated route here is admin-only (store threshold updates, readings,
# incidents). GET /stores and POST /measurements are exempted from the
# gate entirely -- see nginx/internal-gate/telemetry.conf.
allow if {
	common.is_admin
}
