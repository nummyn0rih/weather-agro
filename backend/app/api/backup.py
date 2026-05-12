"""Admin endpoints for database backups (task 6.2).

* ``POST /api/backup/run`` — synchronously run a backup (manual). Returns the
  :class:`~app.db.models.BackupLog` row that was persisted.
* ``GET  /api/backup/list`` — list archives currently stored on Yandex.Disk
  (daily + monthly buckets), with their sizes.

Both endpoints require admin privileges. The scheduled backup is wired
in :mod:`app.scheduler.jobs` and does not go through HTTP.
"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.models import BackupLog, User
from app.db.session import get_db
from app.schemas.backup import (
    BackupListResponse,
    BackupRunResponse,
    RemoteBackupRead,
)
from app.services.backup import runner

router = APIRouter(prefix="/backup", tags=["backup"])
log = structlog.get_logger(__name__)


@router.post(
    "/run",
    response_model=BackupRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run a backup now",
    description=(
        "Admin-only. Synchronously runs `pg_dump | gzip` and uploads the "
        "archive to Yandex.Disk under `<YANDEX_DISK_BACKUP_PATH>/daily/`. "
        "Returns the persisted `BackupLog` row. Errors are reported via the "
        "response body (status='error', error=<message>) rather than a 5xx, "
        "so the admin UI can render them inline."
    ),
)
async def run_backup_now(
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> BackupRunResponse:
    log.info("backup.run.requested", actor_id=admin.id, actor=admin.username)
    await runner.run_backup(kind="manual")
    # The runner persists its own ``BackupLog`` row. Read the most recent one
    # to surface the canonical id/timestamps via the response model.
    row = (
        await session.execute(
            select(BackupLog).order_by(BackupLog.id.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Backup log row not persisted",
        )
    return BackupRunResponse.model_validate(row)


@router.get(
    "/list",
    response_model=BackupListResponse,
    summary="List backups stored on Yandex.Disk",
    description=(
        "Admin-only. Returns every archive currently under the configured "
        "Yandex.Disk backup root, grouped into `daily` and `monthly` buckets."
    ),
)
async def list_backups(
    _admin: Annotated[User, Depends(require_admin)],
) -> BackupListResponse:
    items = await runner.list_remote_backups()
    out = [
        RemoteBackupRead(
            kind=i.kind, name=i.name, path=i.path, size_bytes=i.size_bytes
        )
        for i in items
    ]
    return BackupListResponse(
        items=out,
        total_size_bytes=sum(i.size_bytes for i in out),
        count=len(out),
    )
