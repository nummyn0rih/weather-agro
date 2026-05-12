"""Pydantic schemas for backup endpoints (task 6.2)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BackupRunResponse(BaseModel):
    """Result of a manual backup run."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="BackupLog row id")
    status: Literal["success", "error"]
    kind: Literal["manual", "scheduled"]
    filename: str | None
    size_bytes: int | None
    duration_ms: int | None
    started_at: datetime
    finished_at: datetime | None
    error: str | None


class RemoteBackupRead(BaseModel):
    """One archive currently stored on Yandex.Disk."""

    kind: Literal["daily", "monthly"]
    name: str
    path: str
    size_bytes: int


class BackupListResponse(BaseModel):
    """Aggregate response for :http:get:`/api/backup/list`."""

    items: list[RemoteBackupRead]
    total_size_bytes: int
    count: int
