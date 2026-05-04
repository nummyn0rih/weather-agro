from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import (
    AccessToken,
    LoginRequest,
    RefreshRequest,
    TelegramBindCodeResponse,
    TelegramBindStatus,
    TokenPair,
    UserMe,
)
from app.schemas.invite import InviteAccept, InvitePublic
from app.services import auth as auth_service
from app.services import invites as invites_service
from app.services import telegram_bind

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

    if not user.is_active:
        log.warning(
            "auth.login_inactive",
            username=user.username,
            ip=get_remote_address(request),
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive")

    log.info("auth.login_ok", username=user.username, is_admin=user.is_admin)
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


@router.get(
    "/me",
    response_model=UserMe,
    summary="Current authenticated user",
    description="Returns the profile of the user identified by the access token, "
    "including the `is_admin` and `is_active` flags.",
)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserMe:
    return UserMe(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        telegram_chat_id=user.telegram_chat_id,
        created_at=user.created_at,
    )


@router.get(
    "/invites/{token}",
    response_model=InvitePublic,
    summary="Look up an invite by token (public, used by accept-invite page)",
    description=(
        "Returns the username + is_admin embedded in the invite so the "
        "frontend can pre-fill the registration form. Rate-limited to "
        "10/minute per IP. Returns 404 if the token does not exist, "
        "410 if it has been revoked, accepted, or expired."
    ),
)
@limiter.limit("10/minute")
async def get_invite(
    request: Request,
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InvitePublic:
    invite = await invites_service.get_invite_by_token(session, token)
    return InvitePublic(username=invite.username, is_admin=invite.is_admin)


@router.post(
    "/invites/{token}/accept",
    response_model=TokenPair,
    summary="Accept an invite — create the user and auto-login",
    description=(
        "Public. On success creates the user with the role embedded in the "
        "invite, marks the invite accepted, and returns access+refresh "
        "tokens. Rate-limited to 5/minute per IP."
    ),
)
@limiter.limit("5/minute")
async def accept_invite(
    request: Request,
    token: str,
    body: InviteAccept,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    user = await invites_service.accept_invite(
        session, token=token, password=body.password
    )
    log.info(
        "auth.invite_accept_ok",
        username=user.username,
        is_admin=user.is_admin,
        ip=get_remote_address(request),
    )
    return TokenPair(
        access_token=create_access_token(user.username),
        refresh_token=create_refresh_token(user.username),
    )


@router.post(
    "/telegram/bind-code",
    response_model=TelegramBindCodeResponse,
    summary="Issue one-time Telegram bind code for the current user",
    description="Generates a short-lived numeric code. The user sends "
    "`/start <code>` to the bot to bind their chat_id.",
)
async def issue_telegram_bind_code(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> TelegramBindCodeResponse:
    settings = get_settings()
    code, expires_at = await telegram_bind.issue_bind_code(
        session, user, ttl_seconds=settings.TELEGRAM_BIND_CODE_TTL
    )
    log.info("telegram.bind_code_issued", user_id=user.id)
    return TelegramBindCodeResponse(
        code=code,
        expires_at=expires_at,
        bot_username=None,
    )


@router.get(
    "/telegram/status",
    response_model=TelegramBindStatus,
    summary="Telegram bind status for the current user",
)
async def telegram_status(
    user: Annotated[User, Depends(get_current_user)],
) -> TelegramBindStatus:
    return TelegramBindStatus(
        chat_id=user.telegram_chat_id, bound=user.telegram_chat_id is not None
    )


@router.delete(
    "/telegram/bind",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unbind Telegram chat from the current user",
)
async def unbind_telegram(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    user.telegram_chat_id = None
    user.telegram_bind_code = None
    user.telegram_bind_code_expires_at = None
    await session.commit()
    log.info("telegram.unbound", user_id=user.id)
    return None
