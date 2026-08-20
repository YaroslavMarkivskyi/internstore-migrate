import httpx
from fastapi import Request

DEFAULT_PACKAGE = "catalog"


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
            return False
        return resp.json().get("result", False)


async def get_authz_client(request: Request) -> AuthzClient:
    return request.app.state.authz_client
