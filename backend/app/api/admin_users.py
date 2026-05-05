"""Admin endpoints for managing users (task 6.3.0.2)."""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.models import User
from app.db.session import get_db
from app.schemas.user import UserPasswordReset, UserRead, UserUpdate
from app.services import users as users_service

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
log = structlog.get_logger()


@router.get(
    "",
    response_model=list[UserRead],
    summary="List all users",
    description="Admin-only. Returns every user in the system.",
)
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> list[User]:
    return await users_service.list_users(session)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get a single user",
    description="Admin-only.",
)
async def get_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> User:
    return await users_service.get_user(session, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update a user's role / activity",
    description=(
        "Admin-only. PATCH semantics — only the supplied fields are changed. "
        "Self-lockout protections apply: admins cannot demote or deactivate "
        "themselves, nor can the last active admin be demoted or deactivated."
    ),
)
async def update_user(
    user_id: int,
    body: UserUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    return await users_service.update_user(
        session,
        user_id=user_id,
        is_admin=body.is_admin,
        is_active=body.is_active,
        actor=admin,
    )


@router.post(
    "/{user_id}/reset-password",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Reset a user's password",
    description="Admin-only. Replaces the bcrypt hash with the supplied plaintext.",
)
async def reset_password(
    user_id: int,
    body: UserPasswordReset,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    return await users_service.reset_password(
        session,
        user_id=user_id,
        new_password=body.password,
        actor=admin,
    )
