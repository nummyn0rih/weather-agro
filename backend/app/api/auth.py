from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.schemas.auth import AccessToken, LoginRequest, RefreshRequest, TokenPair
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
log = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Login with username + password",
    description="Returns short-lived access + long-lived refresh JWT. "
    "Rate-limited to 5 requests / minute per IP.",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    user = await auth_service.get_user_by_username(session, body.username)
    if not user or not verify_password(body.password, user.password_hash):
        log.warning(
            "auth.login_failed",
            username=body.username,
            ip=get_remote_address(request),
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    log.info("auth.login_ok", username=user.username)
    return TokenPair(
        access_token=create_access_token(user.username),
        refresh_token=create_refresh_token(user.username),
    )


@router.post(
    "/refresh",
    response_model=AccessToken,
    summary="Exchange refresh token for new access token",
)
async def refresh(body: RefreshRequest) -> AccessToken:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    return AccessToken(access_token=create_access_token(payload["sub"]))


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout (stateless — frontend discards tokens)",
    description="Stateless logout. Token revocation list is not implemented; "
    "the frontend must drop the access and refresh tokens from local storage.",
)
async def logout() -> None:
    return None
