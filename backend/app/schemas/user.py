"""Pydantic schemas for admin user-management endpoints (task 6.3.0.2)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserRead(BaseModel):
    """Public-facing admin view of a user."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime


class UserPasswordReset(BaseModel):
    password: str = Field(..., min_length=8, examples=["new-strong-pass"])


class UserUpdate(BaseModel):
    """PATCH body — only the supplied fields are touched."""

    is_admin: bool | None = None
    is_active: bool | None = None
