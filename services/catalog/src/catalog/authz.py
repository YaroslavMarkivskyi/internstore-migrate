import httpx
from fastapi import Request
from pydantic import BaseModel

DEFAULT_PACKAGE = "catalog"


class AuthzResult(BaseModel):
    # None means no valid token was presented (missing/forged/expired/
    # wrong-issuer) -- distinct from a valid token whose role just isn't
    # allowed. Callers use this to raise 401 vs 403, see auth.py.
    subject: dict | None
    allowed: bool


class AuthzClient:
    def __init__(self, opa_url: str, timeout_seconds: float = 2.0) -> None:
        self._opa_url = opa_url.rstrip("/")
        self._timeout = timeout_seconds

    # Verifies the raw internal token via OPA's common.rego
    # (io.jwt.decode_verify) and returns its claims -- this service no
    # longer decodes/verifies the token itself (see auth.py). Returns
    # None for a missing/forged/expired/wrong-issuer token, same fail-closed
    # shape as `check` below.
    async def identify(self, token: str) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._opa_url}/v1/data/common/subject",
                    json={"input": {"token": token}},
                )
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        result = resp.json().get("result")
        if not isinstance(result, dict) or "sub" not in result or "role" not in result:
            return None
        return result

    # Sends the raw token (not a pre-decoded subject) -- OPA verifies it
    # itself via common.rego's `subject` rule before evaluating the
    # package's `allow` rule, in the same call. Evaluates the whole
    # package (not just /allow) so the response carries `subject`
    # alongside the decision -- an absent subject means the token itself
    # didn't verify (401), not just that the role was denied (403); see
    # AuthzResult and its callers in auth.py/routers.
    async def check(
        self,
        token: str,
        action: str,
        resource: dict,
        package: str = DEFAULT_PACKAGE,
    ) -> AuthzResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._opa_url}/v1/data/{package}",
                    json={"input": {"token": token, "action": action, "resource": resource}},
                )
            resp.raise_for_status()
        except httpx.HTTPError:
            return AuthzResult(subject=None, allowed=False)
        result = resp.json().get("result", {})
        return AuthzResult(subject=result.get("subject"), allowed=result.get("allow", False))


async def get_authz_client(request: Request) -> AuthzClient:
    return request.app.state.authz_client
