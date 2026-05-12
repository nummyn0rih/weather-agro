"""Backup orchestration (task 6.2).

Steps:

1. ``pg_dump`` the live database, piping stdout through ``gzip -9``
   into a temp file (``weather_<YYYY-MM-DD_HHMMSS>.sql.gz``).
2. Upload the archive to Yandex.Disk under ``<backup_root>/daily/``.
3. When ``include_monthly=True`` (or current day is the 1st of the month),
   re-upload the same archive under ``<backup_root>/monthly/<YYYY-MM>.sql.gz``.
4. Rotate: keep newest ``BACKUP_RETENTION_DAILY`` daily archives and
   ``BACKUP_RETENTION_MONTHLY`` monthly archives — older ones are deleted.
5. Persist a :class:`BackupLog` row recording the run.

`DATABASE_URL` is parsed to build the corresponding ``libpq`` connection
arguments (asyncpg → psycopg-style). Credentials are passed via
``PGPASSWORD`` so they do not appear in the process argv.
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import unquote, urlparse

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models import BackupLog
from app.db.session import async_session_factory
from app.services.backup.yandex_disk import (
    RemoteEntry,
    YandexDiskClient,
    YandexDiskError,
    build_client,
)

logger = structlog.get_logger(__name__)

DAILY_SUBDIR = "daily"
MONTHLY_SUBDIR = "monthly"

_DAILY_NAME_RE = re.compile(r"^weather_(\d{4}-\d{2}-\d{2})_(\d{6})\.sql\.gz$")
_MONTHLY_NAME_RE = re.compile(r"^(\d{4}-\d{2})\.sql\.gz$")


@dataclass(frozen=True)
class BackupResult:
    """Outcome of a single backup run."""

    status: str  # 'success' | 'error'
    kind: str    # 'manual' | 'scheduled'
    filename: str | None
    size_bytes: int | None
    duration_ms: int
    started_at: datetime
    finished_at: datetime
    error: str | None
    daily_deleted: int = 0
    monthly_uploaded: bool = False
    monthly_deleted: int = 0


# ── pg_dump → gzip ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class _PgConn:
    host: str
    port: int
    user: str
    password: str
    database: str


def _parse_database_url(url: str) -> _PgConn:
    """Convert ``postgresql+asyncpg://user:pass@host:port/db`` → :class:`_PgConn`."""
    parsed = urlparse(url)
    # Strip SQLAlchemy driver suffix ("postgresql+asyncpg" → "postgresql").
    if "+" in (parsed.scheme or ""):
        scheme = parsed.scheme.split("+", 1)[0]
    else:
        scheme = parsed.scheme
    if scheme not in ("postgresql", "postgres"):
        raise ValueError(f"unsupported DATABASE_URL scheme: {parsed.scheme!r}")
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    database = (parsed.path or "/").lstrip("/")
    if not database:
        raise ValueError("DATABASE_URL is missing database name")
    return _PgConn(host=host, port=port, user=user, password=password, database=database)


async def _pg_dump_to_gzip(conn: _PgConn, dest_path: str) -> None:
    """Run ``pg_dump | gzip -9`` writing the gzipped SQL to ``dest_path``.

    Raises :class:`RuntimeError` on non-zero exit from either process.
    """
    env = os.environ.copy()
    env["PGPASSWORD"] = conn.password

    pg = await asyncio.create_subprocess_exec(
        "pg_dump",
        "--host", conn.host,
        "--port", str(conn.port),
        "--username", conn.user,
        "--no-password",
        "--format=plain",
        "--no-owner",
        "--no-privileges",
        conn.database,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    with open(dest_path, "wb") as out:
        gz = await asyncio.create_subprocess_exec(
            "gzip", "-9", "-c",
            stdin=pg.stdout,
            stdout=out,
            stderr=asyncio.subprocess.PIPE,
        )
        # Closing pg.stdout from the parent lets pg_dump observe a clean EOF
        # only after gzip reads everything — keep it open for the await.
        pg_err = (await pg.communicate())[1]
        _gz_out, gz_err = await gz.communicate()

    if pg.returncode != 0:
        raise RuntimeError(
            f"pg_dump exited {pg.returncode}: {pg_err.decode(errors='replace').strip()}"
        )
    if gz.returncode != 0:
        raise RuntimeError(
            f"gzip exited {gz.returncode}: {gz_err.decode(errors='replace').strip()}"
        )


# ── rotation ───────────────────────────────────────────────────────────


def _daily_key(entry: RemoteEntry) -> str:
    m = _DAILY_NAME_RE.match(entry.name)
    if not m:
        return ""
    return f"{m.group(1)}_{m.group(2)}"


def _monthly_key(entry: RemoteEntry) -> str:
    m = _MONTHLY_NAME_RE.match(entry.name)
    if not m:
        return ""
    return m.group(1)


async def _rotate(
    client: YandexDiskClient,
    subdir: str,
    keep: int,
    key_fn,
) -> int:
    """Keep the newest ``keep`` files by ``key_fn`` order in ``subdir``.

    Returns the number of objects deleted.
    """
    dir_path = client.join(subdir) + "/"
    entries = await client.list_dir(dir_path)
    keyed = [
        (key_fn(e), e) for e in entries if not e.is_dir and key_fn(e)
    ]
    keyed.sort(key=lambda kv: kv[0], reverse=True)
    deleted = 0
    for _key, entry in keyed[keep:]:
        try:
            await client.delete(entry.path)
            deleted += 1
        except YandexDiskError:
            logger.exception("backup.rotation_delete_failed", remote_path=entry.path)
    return deleted


# ── orchestration ──────────────────────────────────────────────────────


async def _persist_log(
    session_factory: async_sessionmaker[AsyncSession], result: BackupResult
) -> int:
    async with session_factory() as session:
        row = BackupLog(
            started_at=result.started_at,
            finished_at=result.finished_at,
            status=result.status,
            kind=result.kind,
            filename=result.filename,
            size_bytes=result.size_bytes,
            duration_ms=result.duration_ms,
            error=result.error,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id


async def run_backup(
    *,
    kind: str = "scheduled",
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    include_monthly: bool | None = None,
    now: datetime | None = None,
) -> BackupResult:
    """Execute a full backup cycle. Always persists a :class:`BackupLog` row.

    Args:
        kind: ``'manual'`` (user-triggered) or ``'scheduled'`` (cron).
        session_factory: override for tests; defaults to global factory.
        include_monthly: force monthly upload regardless of day; if ``None``,
            uploads monthly only when ``now.day == 1``.
        now: override for the timestamp source (tests).
    """
    factory = session_factory or async_session_factory
    started_at = now or datetime.now(UTC)
    stamp = started_at.strftime("%Y-%m-%d_%H%M%S")
    filename = f"weather_{stamp}.sql.gz"
    monthly_name = started_at.strftime("%Y-%m") + ".sql.gz"
    should_monthly = (
        include_monthly if include_monthly is not None else started_at.day == 1
    )

    t0 = time.monotonic()
    status = "success"
    error: str | None = None
    size_bytes: int | None = None
    daily_deleted = 0
    monthly_uploaded = False
    monthly_deleted = 0
    daily_remote: str | None = None

    settings = get_settings()
    conn = _parse_database_url(settings.DATABASE_URL)

    try:
        with tempfile.TemporaryDirectory(prefix="weather-backup-") as tmpdir:
            local_path = os.path.join(tmpdir, filename)
            logger.info(
                "backup.pg_dump.start", filename=filename, kind=kind
            )
            await _pg_dump_to_gzip(conn, local_path)
            size_bytes = os.path.getsize(local_path)
            logger.info(
                "backup.pg_dump.done",
                filename=filename,
                size_bytes=size_bytes,
            )

            async with build_client() as client:
                await client.ensure_dir(
                    client.join(DAILY_SUBDIR) + "/"
                )
                daily_remote = client.join(DAILY_SUBDIR, filename)
                await client.upload(local_path, daily_remote)

                if should_monthly:
                    await client.ensure_dir(
                        client.join(MONTHLY_SUBDIR) + "/"
                    )
                    monthly_remote = client.join(MONTHLY_SUBDIR, monthly_name)
                    await client.upload(local_path, monthly_remote)
                    monthly_uploaded = True

                daily_deleted = await _rotate(
                    client,
                    DAILY_SUBDIR,
                    keep=settings.BACKUP_RETENTION_DAILY,
                    key_fn=_daily_key,
                )
                monthly_deleted = await _rotate(
                    client,
                    MONTHLY_SUBDIR,
                    keep=settings.BACKUP_RETENTION_MONTHLY,
                    key_fn=_monthly_key,
                )
    except Exception as exc:
        status = "error"
        error = f"{exc.__class__.__name__}: {exc}"
        logger.exception("backup.failed", kind=kind, filename=filename)

    finished_at = datetime.now(UTC)
    duration_ms = int((time.monotonic() - t0) * 1000)
    result = BackupResult(
        status=status,
        kind=kind,
        filename=filename if status == "success" else None,
        size_bytes=size_bytes if status == "success" else None,
        duration_ms=duration_ms,
        started_at=started_at,
        finished_at=finished_at,
        error=error,
        daily_deleted=daily_deleted,
        monthly_uploaded=monthly_uploaded,
        monthly_deleted=monthly_deleted,
    )

    try:
        log_id = await _persist_log(factory, result)
        logger.info(
            "backup.done",
            kind=kind,
            status=status,
            filename=result.filename,
            size_bytes=size_bytes,
            duration_ms=duration_ms,
            daily_deleted=daily_deleted,
            monthly_uploaded=monthly_uploaded,
            monthly_deleted=monthly_deleted,
            backup_log_id=log_id,
        )
    except Exception:
        logger.exception("backup.log_write_failed")

    return result


# ── listing ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RemoteBackup:
    kind: str  # 'daily' | 'monthly'
    name: str
    path: str
    size_bytes: int


async def list_remote_backups(
    client: YandexDiskClient | None = None,
) -> list[RemoteBackup]:
    """Return all backup archives on Yandex.Disk under ``daily/`` and ``monthly/``."""

    @asynccontextmanager
    async def _ctx():
        if client is not None:
            yield client
        else:
            async with build_client() as c:
                yield c

    out: list[RemoteBackup] = []
    async with _ctx() as c:
        for subdir, kind, key_fn in (
            (DAILY_SUBDIR, "daily", _daily_key),
            (MONTHLY_SUBDIR, "monthly", _monthly_key),
        ):
            try:
                entries = await c.list_dir(c.join(subdir) + "/")
            except YandexDiskError:
                logger.exception("backup.list_failed", subdir=subdir)
                continue
            for e in entries:
                if e.is_dir or not key_fn(e):
                    continue
                out.append(
                    RemoteBackup(
                        kind=kind, name=e.name, path=e.path, size_bytes=e.size
                    )
                )
    out.sort(key=lambda r: (r.kind, r.name), reverse=True)
    return out
