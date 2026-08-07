import httpx
from fastapi import Request

# STR-140: thin wrapper around the OPA sidecar running alongside this
# service (see docker-compose.yml's payments-opa, and
# policies/payments.rego for the policy itself) -- a localhost call, not a
# network hop to a centralized authorization service. Per-service
# duplication (not a shared pip package), same convention as this repo's
# kafka.py/outbox.py.
DEFAULT_PACKAGE = "payments"


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
