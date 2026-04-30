"""One-time bind code lifecycle for Telegram chat linking.

The web UI generates a short-lived numeric code via :func:`issue_bind_code` and
shows it to the operator. The operator sends ``/start <code>`` to the bot;
:func:`consume_bind_code` validates the code, links ``telegram_chat_id`` to the
user and clears the code so it cannot be reused.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User

CODE_LENGTH = 8


def _generate_code() -> str:
    """Random 8-digit numeric code (URL/keyboard friendly)."""
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


async def issue_bind_code(
    session: AsyncSession,
    user: User,
    *,
    ttl_seconds: int,
    now: datetime | None = None,
) -> tuple[str, datetime]:
    """Generate fresh code for ``user``. Overwrites any previous unused code."""
    moment = now or datetime.now(UTC)
    code = _generate_code()
    expires_at = moment + timedelta(seconds=ttl_seconds)
    user.telegram_bind_code = code
    user.telegram_bind_code_expires_at = expires_at
    await session.commit()
    await session.refresh(user)
    return code, expires_at


async def consume_bind_code(
    session: AsyncSession,
    code: str,
    chat_id: int,
    *,
    now: datetime | None = None,
) -> User | None:
    """Bind ``chat_id`` to user matching ``code``. Returns the user or None."""
    moment = now or datetime.now(UTC)
    stmt = select(User).where(User.telegram_bind_code == code)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        return None
    if user.telegram_bind_code_expires_at is None:
        return None
    expires_at = user.telegram_bind_code_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at < moment:
        return None

    # Detach this chat_id from any other user (one chat → one user invariant).
    detach = select(User).where(
        User.telegram_chat_id == chat_id, User.id != user.id
    )
    for other in (await session.execute(detach)).scalars().all():
        other.telegram_chat_id = None

    user.telegram_chat_id = chat_id
    user.telegram_bind_code = None
    user.telegram_bind_code_expires_at = None
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_chat_id(
    session: AsyncSession, chat_id: int
) -> User | None:
    """Lookup the bound user by Telegram chat_id."""
    stmt = select(User).where(User.telegram_chat_id == chat_id)
    return (await session.execute(stmt)).scalar_one_or_none()
