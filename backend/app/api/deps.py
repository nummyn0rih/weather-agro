from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db
from app.services import auth as auth_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _token_invalidated(payload: dict, user: User) -> bool:
    """Return True if the user's tokens were invalidated after this token was issued.

    JWT `iat` is integer-seconds while `tokens_invalidated_at` may carry
    sub-second precision. A token whose `iat` falls inside the same second as
    `tokens_invalidated_at` could have been minted either side of the
    invalidation — we reject it to stay on the safe side (security gate).
    Concretely: a token is rejected when
    `int(iat) <= int(tokens_invalidated_at.timestamp())`.
    """
    invalidated_at = user.tokens_invalidated_at
    if invalidated_at is None:
        return False
    if invalidated_at.tzinfo is None:
        # SQLite (used in tests) drops tzinfo on read; treat as UTC.
        invalidated_at = invalidated_at.replace(tzinfo=timezone.utc)
    iat_raw = payload.get("iat")
    if iat_raw is None:
        return True
    return int(iat_raw) <= int(invalidated_at.timestamp())


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(token, "access")
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    username = payload.get("sub")
    if not username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")

    user = await auth_service.get_user_by_username(session, username)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive")
    if _token_invalidated(payload, user):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalidated")
    return user


async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Restrict endpoint to admin users.

    Inactive users are rejected by `get_current_user` upstream (401).
    Non-admin authenticated users get 403.
    """
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin privileges required")
    return user
