"""Admin user-management service (task 6.3.0.2).

Self-lockout protections enforced here, not in the route layer:
  - Admin cannot strip their own `is_admin`.
  - Admin cannot deactivate themselves.
  - Cannot strip `is_admin` from the last active admin.
  - Cannot deactivate the last active admin.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import User

log = structlog.get_logger()


async def list_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).order_by(User.created_at.asc()))
    return list(result.scalars().all())


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


async def _active_admin_count(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count(User.id)).where(
            User.is_admin.is_(True), User.is_active.is_(True)
        )
    )
    return int(result.scalar_one())


async def update_user(
    session: AsyncSession,
    *,
    user_id: int,
    is_admin: bool | None,
    is_active: bool | None,
    actor: User,
) -> User:
    target = await get_user(session, user_id)

    # Self-lockout: admin can't demote / deactivate themselves.
    if target.id == actor.id:
        if is_admin is False:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "You cannot remove admin privileges from yourself",
            )
        if is_active is False:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "You cannot deactivate yourself",
            )

    # Last-admin guard: only matters if the change would reduce the
    # active-admin count from this user.
    losing_admin = is_admin is False and target.is_admin
    being_deactivated = is_active is False and target.is_active
    if (losing_admin or being_deactivated) and target.is_admin and target.is_active:
        if await _active_admin_count(session) <= 1:
            if losing_admin:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Cannot remove admin privileges from the last active admin",
                )
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Cannot deactivate the last active admin",
            )

    changed: dict[str, object] = {}
    invalidated_tokens = False
    if is_admin is not None and is_admin != target.is_admin:
        target.is_admin = is_admin
        changed["is_admin"] = is_admin
    if is_active is not None and is_active != target.is_active:
        target.is_active = is_active
        changed["is_active"] = is_active
        if is_active is False:
            target.tokens_invalidated_at = datetime.now(timezone.utc)
            invalidated_tokens = True

    if changed:
        await session.commit()
        await session.refresh(target)
        log.info(
            "admin.user_updated",
            target_id=target.id,
            target_username=target.username,
            actor=actor.username,
            **changed,
        )
        if invalidated_tokens:
            log.info(
                "admin.tokens_invalidated",
                reason="deactivated",
                target_id=target.id,
                actor=actor.username,
            )
    return target


async def reset_password(
    session: AsyncSession,
    *,
    user_id: int,
    new_password: str,
    actor: User,
) -> User:
    target = await get_user(session, user_id)
    target.password_hash = hash_password(new_password)
    await session.commit()
    await session.refresh(target)
    log.info(
        "admin.user_password_reset",
        target_id=target.id,
        target_username=target.username,
        actor=actor.username,
    )
    return target
