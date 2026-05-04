"""Admin endpoints for managing user invites."""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.schemas.invite import InviteCreate, InviteCreated, InviteRead
from app.services import invites as invites_service

router = APIRouter(prefix="/admin/invites", tags=["admin-invites"])
log = structlog.get_logger()


@router.post(
    "",
    response_model=InviteCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a single-use invite for a new user",
    description=(
        "Admin-only. Generates a 7-day URL-safe token and returns the "
        "absolute invite URL pointing at the frontend's accept-invite page. "
        "Returns 409 if the username is already in use or already has an "
        "active pending invite."
    ),
)
async def create_invite(
    body: InviteCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> InviteCreated:
    invite = await invites_service.create_invite(
        session,
        username=body.username,
        is_admin=body.is_admin,
        created_by=admin,
    )
    settings = get_settings()
    return InviteCreated(
        id=invite.id,
        token=invite.token,
        invite_url=invites_service.build_invite_url(settings.FRONTEND_URL, invite.token),
        username=invite.username,
        is_admin=invite.is_admin,
        expires_at=invite.expires_at,
    )


@router.get(
    "",
    response_model=list[InviteRead],
    summary="List all invites with computed status",
    description=(
        "Admin-only. Each item carries a computed status — "
        "`pending` / `accepted` / `revoked` / `expired` — derived on the fly."
    ),
)
async def list_invites(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> list[InviteRead]:
    rows = await invites_service.list_invites(session)
    return [
        InviteRead(
            id=row.id,
            username=row.username,
            is_admin=row.is_admin,
            created_at=row.created_at,
            expires_at=row.expires_at,
            accepted_at=row.accepted_at,
            revoked_at=row.revoked_at,
            status=invites_service.compute_status(row),
        )
        for row in rows
    ]


@router.delete(
    "/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a pending invite",
    description="Admin-only. 404 if the invite is missing or already accepted.",
)
async def revoke_invite(
    invite_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    await invites_service.revoke_invite(session, invite_id=invite_id)
    return None
