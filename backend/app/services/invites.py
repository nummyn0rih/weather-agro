"""Invite service: create / revoke / accept invites for new users."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import Invite, User
from app.schemas.invite import InviteStatus

INVITE_TTL = timedelta(days=7)
TOKEN_BYTES = 32  # → 43-char URL-safe string

log = structlog.get_logger()


def _as_utc(value: datetime) -> datetime:
    """Coerce a possibly naive datetime (e.g. SQLite-stored) to tz-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def compute_status(invite: Invite, *, now: datetime | None = None) -> InviteStatus:
    """Derive invite state on the fly. Order: revoked → accepted → expired → pending."""
    moment = now or datetime.now(timezone.utc)
    if invite.revoked_at is not None:
        return "revoked"
    if invite.accepted_at is not None:
        return "accepted"
    if _as_utc(invite.expires_at) <= moment:
        return "expired"
    return "pending"


async def _username_taken(session: AsyncSession, username: str) -> bool:
    result = await session.execute(
        select(User.id).where(User.username == username, User.is_active.is_(True))
    )
    return result.scalar_one_or_none() is not None


async def _active_pending_invite(
    session: AsyncSession, username: str
) -> Invite | None:
    """Pending = not accepted, not revoked, not expired."""
    result = await session.execute(
        select(Invite).where(
            Invite.username == username,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    for invite in result.scalars():
        if _as_utc(invite.expires_at) > now:
            return invite
    return None


async def create_invite(
    session: AsyncSession,
    *,
    username: str,
    is_admin: bool,
    created_by: User,
) -> Invite:
    if await _username_taken(session, username):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Username already taken by an active user"
        )
    if await _active_pending_invite(session, username) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An active invite already exists for this username; revoke it first",
        )

    invite = Invite(
        username=username,
        is_admin=is_admin,
        token=secrets.token_urlsafe(TOKEN_BYTES),
        created_by_id=created_by.id,
        expires_at=datetime.now(timezone.utc) + INVITE_TTL,
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    log.info(
        "invite.created",
        invite_id=invite.id,
        username=username,
        is_admin=is_admin,
        created_by=created_by.username,
    )
    return invite


async def revoke_invite(session: AsyncSession, *, invite_id: int) -> None:
    invite = await session.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if invite.accepted_at is not None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Invite already accepted, cannot revoke"
        )
    if invite.revoked_at is not None:
        return  # idempotent
    invite.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    log.info("invite.revoked", invite_id=invite.id, username=invite.username)


async def get_invite_by_token(session: AsyncSession, token: str) -> Invite:
    """Fetch an invite by token if still pending. Raises 404/410 otherwise."""
    result = await session.execute(select(Invite).where(Invite.token == token))
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    state = compute_status(invite)
    if state != "pending":
        raise HTTPException(status.HTTP_410_GONE, f"Invite is {state}")
    return invite


async def list_invites(session: AsyncSession) -> list[Invite]:
    result = await session.execute(select(Invite).order_by(Invite.created_at.desc()))
    return list(result.scalars().all())


async def accept_invite(
    session: AsyncSession, *, token: str, password: str
) -> User:
    invite = await get_invite_by_token(session, token)

    # Race: someone else may have registered the same username after the
    # invite was minted. Re-check before creating.
    if await _username_taken(session, invite.username):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Username already taken by an active user"
        )

    user = User(
        username=invite.username,
        password_hash=hash_password(password),
        is_admin=invite.is_admin,
        is_active=True,
    )
    session.add(user)
    invite.accepted_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)
    log.info(
        "invite.accepted",
        invite_id=invite.id,
        username=user.username,
        is_admin=user.is_admin,
    )
    return user


def build_invite_url(frontend_url: str, token: str) -> str:
    base = frontend_url.rstrip("/")
    return f"{base}/accept-invite/{token}"
