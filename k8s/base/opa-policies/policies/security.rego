package security

import future.keywords.if
import data.common

default allow := false

# /users and /visit-log are admin-only today (mirrors require_admin's
# previous router-level behavior, see routers/users.py and
# routers/visit_log.py).
allow if {
	common.is_admin
}
