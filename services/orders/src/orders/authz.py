import httpx
from fastapi import Request

# Thin wrapper around the OPA sidecar running alongside this service (see
# docker-compose.yml's orders-opa, and policies/orders.rego) -- a
# localhost call, not a network hop to a centralized authorization
# service. Per-service duplication (not a shared pip package), same
# convention as this repo's kafka.py/outbox.py.
#
# The only call site left is routers/orders.py's get_order -- a
# resource-ownership check (owner_id lives in this service's own DB,
# unreachable from orders-gate) -- everything else (route-level
# admin-only/admin-or-assistant/any-authenticated tiers, previously
# policies/checkout.rego) moved to orders-gate + orders-verify ahead of
# this app entirely. `package` stays a per-call argument (not hardcoded
# inline) purely so this client stays reusable if a second call site ever
# needs it.
DEFAULT_PACKAGE = "orders"


class AuthzClient:
    def __init__(self, opa_url: str, timeout_seconds: float = 2.0) -> None:
        self._opa_url = opa_url.rstrip("/")
        self._timeout = timeout_seconds

    async def check(
        self,
        subject: dict,
        action: str,
        resource: dict,
        package: str = DEFAULT_PACKAGE,
    ) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._opa_url}/v1/data/{package}/allow",
                    json={"input": {"subject": subject, "action": action, "resource": resource}},
                )
            resp.raise_for_status()
        except httpx.HTTPError:
            # Fail closed: sidecar unreachable/erroring (startup race,
            # crash, malformed policy) must deny, not silently allow. Same
            # fail-closed pattern as auth-backend's RevocationChecker (see
            # services/auth-backend/src/auth_backend/auth/revocation.py).
            return False
        return resp.json().get("result", False)


async def get_authz_client(request: Request) -> AuthzClient:
    return request.app.state.authz_client
