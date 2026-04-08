from enum import Enum

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import verify_token

bearer_scheme = HTTPBearer(auto_error=False)


class Role(str, Enum):
    IO = "IO"
    SHO = "SHO"
    DYSP = "DYSP"
    SP = "SP"
    ADMIN = "ADMIN"
    READONLY = "READONLY"


ROLE_PERMISSIONS = {
    Role.IO: ["fir:read", "fir:write", "fir:upload", "chargesheet:read"],
    Role.SHO: ["fir:read", "fir:write", "fir:upload", "fir:approve", "chargesheet:read", "chargesheet:write"],
    Role.DYSP: ["fir:read", "fir:approve", "chargesheet:read", "chargesheet:approve", "dashboard:read"],
    Role.SP: ["fir:read", "fir:approve", "chargesheet:read", "chargesheet:approve", "dashboard:read", "user:manage"],
    Role.ADMIN: ["fir:read", "fir:write", "fir:upload", "fir:approve", "chargesheet:read", "chargesheet:write",
                 "chargesheet:approve", "dashboard:read", "user:manage", "admin:all"],
    Role.READONLY: ["fir:read", "chargesheet:read", "dashboard:read"],
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    return {
        "username": payload.get("sub"),
        "role": payload.get("role"),
        "district": payload.get("district"),
        "full_name": payload.get("full_name"),
    }


def require_role(*allowed_roles: Role):
    async def dependency(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user['role']} not authorized",
            )
        return user
    return dependency
