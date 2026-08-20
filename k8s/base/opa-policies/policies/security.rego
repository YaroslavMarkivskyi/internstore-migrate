package security

import future.keywords.if
import data.common

default allow := false

# Exported so security-verify (internal-gate) can tell "no valid token"
# (subject undefined -> 401) apart from "valid token, wrong role"
# (subject present, allow false -> 403) in one call -- see
# services/internal-gate and nginx/internal-gate/security.conf.
subject := common.subject

# /users, /visit-log and /warehouses are admin-only regardless of method
# (including their GET routes) -- see security-gate's nginx config, which
# only exempts /auth/* (the hardware-simulator endpoints, never gated at
# all).
allow if {
	common.is_admin
}
