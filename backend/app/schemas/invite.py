from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

InviteStatus = Literal["pending", "accepted", "revoked", "expired"]


class InviteCreate(BaseModel):
    username: EmailStr = Field(..., examples=["new.user@example.com"])
    is_admin: bool = False


class InviteAccept(BaseModel):
    password: str = Field(..., min_length=8, examples=["strongpass"])


class InvitePublic(BaseModel):
    """Returned to the public on `GET /api/auth/invites/{token}`."""

    username: EmailStr
    is_admin: bool


class InviteCreated(BaseModel):
    """Returned to admin on `POST /api/admin/invites`."""

    id: int
    token: str
    invite_url: str
    username: EmailStr
    is_admin: bool
    expires_at: datetime


class InviteRead(BaseModel):
    """List item for admin — token deliberately omitted."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: EmailStr
    is_admin: bool
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None = None
    revoked_at: datetime | None = None
    status: InviteStatus
