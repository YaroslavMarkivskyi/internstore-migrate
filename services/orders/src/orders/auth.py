from typing import Annotated, Literal

from fastapi import Header, HTTPException
from pydantic import BaseModel


class InternalClaims(BaseModel):
    sub: str
    role: Literal["customer", "admin", "guest", "assistant"]


# Identity extraction, not verification: orders-gate (nginx `auth_request`)
# + orders-verify (services/internal-gate) + orders-opa
# (policies/orders.rego) already verified the caller's internal token and
# forwarded X-User-Id/X-User-Role as trusted headers -- this app is
# unreachable on any other path (HOST=127.0.0.1, see docker-compose.yml).
# Business logic here still needs to know *who* the caller is (own cart,
# own orders, the resource-ownership check on GET /orders/{id} --
# routers/orders.py's get_order), it just doesn't verify that identity
# itself anymore.
def get_internal_claims(
    x_user_id: Annotated[str | None, Header()] = None,
    x_user_role: Annotated[str | None, Header()] = None,
) -> InternalClaims:
    if x_user_id is None or x_user_role is None or x_user_role not in ("customer", "admin", "guest", "assistant"):
        # Should be unreachable in practice: every route that depends on
        # this always sits behind orders-gate's @gated location, which
        # never forwards a request without both headers set (auth_request
        # already 401'd it otherwise). Fails closed instead of trusting a
        # malformed identity if that invariant is ever broken.
        raise HTTPException(status_code=401, detail="Missing internal identity")
    return InternalClaims(sub=x_user_id, role=x_user_role)
