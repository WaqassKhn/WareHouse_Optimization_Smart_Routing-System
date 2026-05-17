from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.core.security import create_access_token, decode_access_token, get_password_hash, verify_password
from app.schemas import Role, TokenResponse, UserPrincipal


router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

DEMO_USERS = {
    "admin@supplychain.ai": {
        "hashed_password": get_password_hash("admin123"),
        "role": Role.admin,
    },
    "planner@supplychain.ai": {
        "hashed_password": get_password_hash("planner123"),
        "role": Role.planner,
    },
}


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    user = DEMO_USERS.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token(subject=form_data.username, role=user["role"].value)
    return TokenResponse(access_token=token, role=user["role"])


def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPrincipal:
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        role = Role(payload.get("role", "viewer"))
        if not email:
            raise ValueError("Missing token subject")
        return UserPrincipal(email=email, role=role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_roles(*roles: Role) -> Callable:
    def dependency(user: UserPrincipal = Depends(get_current_user)) -> UserPrincipal:
        if user.role == Role.admin or user.role in roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User role is not authorized for this operation",
        )

    return dependency

