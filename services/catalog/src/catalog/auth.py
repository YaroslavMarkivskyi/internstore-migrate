from typing import Annotated, Literal
from enum import StrEnum

import jwt
from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

ISSUER = "internstore-gateway"

class InternalRole(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"
    GUEST = "guest"


class InternalClaims(BaseModel):
    sub: str
    role: Literal[
        InternalRole.CUSTOMER,
        InternalRole.ADMIN,
        InternalRole.GUEST,
    ]


class InternalTokenException(HTTPException):
    def __init__(self, detail: str = "Invalid internal token"):
        super().__init__(status_code=401, detail=detail)


class PermissionDeniedException(HTTPException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=403, detail=detail)


def verify_internal_token(
        token: str, 
        secret: str,
    ) -> InternalClaims:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            issuer=ISSUER,
        )
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid internal token") from exc

    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or role not in (
        InternalRole.CUSTOMER,
        InternalRole.ADMIN,
        InternalRole.GUEST,
    ):
        raise ValueError("Invalid internal token claims")
    return InternalClaims(sub=sub, role=role)


def get_internal_claims(
        request: Request,
        x_internal_token: Annotated[str | None, Header()] = None,
) -> InternalClaims:
    if x_internal_token is None:
        raise InternalTokenException(detail="Missing internal token")
    secret: str = request.app.state.settings.internal_token_secret
    try:
        return verify_internal_token(x_internal_token, secret)
    except ValueError as exc:
        raise InternalTokenException(detail="Invalid internal token") from exc


def require_admin(
        claims: Annotated[
            InternalClaims,
            Depends(get_internal_claims),
        ],
) -> InternalClaims:
    if claims.role != InternalRole.ADMIN:
        raise PermissionDeniedException(detail="Admin role required")
    return claims
