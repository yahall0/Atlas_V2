from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.core.rbac import get_current_user

router = APIRouter(tags=["auth"])

# Pilot hardcoded users — will migrate to DB lookup later
_PILOT_USERS = [
    {"username": "admin", "password": "atlas2025", "role": "ADMIN",
     "district": "Ahmedabad", "full_name": "ATLAS Admin"},
    {"username": "io_sanand", "password": "atlas2025", "role": "IO",
     "district": "Ahmedabad", "full_name": "Sanand IO"},
    {"username": "sho_sanand", "password": "atlas2025", "role": "SHO",
     "district": "Ahmedabad", "full_name": "Sanand SHO"},
]

# Hash passwords at module load
USERS = []
for u in _PILOT_USERS:
    USERS.append({
        "username": u["username"],
        "password_hash": hash_password(u["password"]),
        "role": u["role"],
        "district": u["district"],
        "full_name": u["full_name"],
    })


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def _find_user(username: str) -> dict | None:
    for u in USERS:
        if u["username"] == username:
            return u
    return None


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    user = _find_user(body.username)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token_data = {
        "sub": user["username"],
        "role": user["role"],
        "district": user["district"],
        "full_name": user["full_name"],
    }
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh")
def refresh(body: RefreshRequest):
    payload = verify_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    token_data = {
        "sub": payload["sub"],
        "role": payload["role"],
        "district": payload.get("district"),
        "full_name": payload.get("full_name"),
    }
    return {"access_token": create_access_token(token_data), "token_type": "bearer"}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "username": user["username"],
        "role": user["role"],
        "district": user["district"],
        "full_name": user["full_name"],
    }
