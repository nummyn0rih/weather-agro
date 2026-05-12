"""Happy-path tests for backup endpoints + runner (task 6.2).

External I/O (pg_dump, Yandex.Disk) is replaced with in-process fakes so
the tests are hermetic. The fakes still exercise the orchestration:
filename building, BackupLog persistence, rotation, monthly upload,
PROPFIND XML parsing.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import auth as auth_module
from app.api.deps import get_current_user
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import BackupLog, User
from app.db.session import get_db
from app.main import app
from app.services.backup import runner as backup_runner
from app.services.backup.yandex_disk import RemoteEntry, _parse_propfind


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    auth_module.limiter.reset()


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sc: Base.metadata.create_all(
                sc, tables=[User.__table__, BackupLog.__table__]
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def admin_user(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            username="admin@example.com",
            password_hash=hash_password("adminpass"),
            is_admin=True,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def regular_user(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            username="bob@example.com",
            password_hash=hash_password("bobpass"),
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
def client_factory(session_factory):
    def _build(current_user: User | None = None) -> TestClient:
        async def fake_get_db() -> AsyncIterator:
            async with session_factory() as session:
                yield session

        async def fake_current_user() -> User:
            if current_user is None:
                from fastapi import HTTPException, status

                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
            return current_user

        app.dependency_overrides[get_db] = fake_get_db
        if current_user is not None:
            app.dependency_overrides[get_current_user] = fake_current_user
        return TestClient(app)

    yield _build
    app.dependency_overrides.clear()


# ── runner happy path ───────────────────────────────────────────────


class _FakeClient:
    """In-memory stand-in for :class:`YandexDiskClient`."""

    def __init__(self, *, monthly_existing: list[str] | None = None) -> None:
        self.uploads: list[tuple[str, str]] = []
        self.deletes: list[str] = []
        self._daily_existing: list[RemoteEntry] = []
        self._monthly_existing: list[RemoteEntry] = [
            RemoteEntry(
                name=name,
                path=f"/weather-app-backups/monthly/{name}",
                size=10,
                is_dir=False,
            )
            for name in (monthly_existing or [])
        ]

    @property
    def backup_root(self) -> str:
        return "/weather-app-backups/"

    def join(self, *parts: str) -> str:
        path = self.backup_root.rstrip("/")
        for part in parts:
            path = path + "/" + part.strip("/")
        return path

    async def ensure_dir(self, path: str) -> None:
        return None

    async def upload(self, local_path: str, remote_path: str) -> int:
        import os

        size = os.path.getsize(local_path)
        self.uploads.append((local_path, remote_path))
        return size

    async def list_dir(self, path: str):
        if path.endswith("/daily/"):
            return list(self._daily_existing)
        if path.endswith("/monthly/"):
            return list(self._monthly_existing)
        return []

    async def delete(self, remote_path: str) -> None:
        self.deletes.append(remote_path)


@pytest_asyncio.fixture
async def fake_yandex(monkeypatch):
    """Patch ``build_client`` to yield a shared FakeClient."""
    fake = _FakeClient()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _ctx():
        yield fake

    monkeypatch.setattr(
        "app.services.backup.runner.build_client", _ctx
    )
    return fake


@pytest_asyncio.fixture
async def fake_pg_dump(monkeypatch):
    """Replace pg_dump|gzip with a tiny byte writer."""

    async def _fake_dump(conn, dest_path):
        with open(dest_path, "wb") as f:
            f.write(b"-- fake gzip dump\n" * 16)

    monkeypatch.setattr(
        "app.services.backup.runner._pg_dump_to_gzip", _fake_dump
    )


async def test_run_backup_happy_path(
    session_factory, fake_yandex, fake_pg_dump
) -> None:
    """End-to-end runner: daily upload, log row, no rotation needed."""
    result = await backup_runner.run_backup(
        kind="manual",
        session_factory=session_factory,
        now=datetime(2026, 5, 12, 4, 0, 0, tzinfo=UTC),
    )

    assert result.status == "success"
    assert result.kind == "manual"
    assert result.filename == "weather_2026-05-12_040000.sql.gz"
    assert result.size_bytes is not None and result.size_bytes > 0
    assert result.error is None
    # Day 12 → no monthly upload.
    assert result.monthly_uploaded is False
    assert (
        fake_yandex.uploads
        and fake_yandex.uploads[0][1]
        == "/weather-app-backups/daily/weather_2026-05-12_040000.sql.gz"
    )

    async with session_factory() as session:
        row = (await session.execute(select(BackupLog))).scalar_one()
        assert row.status == "success"
        assert row.kind == "manual"
        assert row.filename == "weather_2026-05-12_040000.sql.gz"
        assert row.size_bytes == result.size_bytes


async def test_run_backup_first_of_month_uploads_monthly(
    session_factory, fake_yandex, fake_pg_dump
) -> None:
    result = await backup_runner.run_backup(
        kind="scheduled",
        session_factory=session_factory,
        now=datetime(2026, 6, 1, 4, 0, 0, tzinfo=UTC),
    )

    assert result.status == "success"
    assert result.monthly_uploaded is True
    remote_paths = [r for _l, r in fake_yandex.uploads]
    assert (
        "/weather-app-backups/daily/weather_2026-06-01_040000.sql.gz"
        in remote_paths
    )
    assert "/weather-app-backups/monthly/2026-06.sql.gz" in remote_paths


async def test_run_backup_persists_error_log(
    session_factory, monkeypatch, fake_yandex
) -> None:
    """pg_dump failure → BackupLog row with status='error', filename=None."""

    async def _boom(conn, dest_path):
        raise RuntimeError("pg_dump exited 1: connection refused")

    monkeypatch.setattr(
        "app.services.backup.runner._pg_dump_to_gzip", _boom
    )

    result = await backup_runner.run_backup(
        kind="manual",
        session_factory=session_factory,
        now=datetime(2026, 5, 12, 4, 0, 0, tzinfo=UTC),
    )
    assert result.status == "error"
    assert result.filename is None
    assert result.error and "connection refused" in result.error

    async with session_factory() as session:
        row = (await session.execute(select(BackupLog))).scalar_one()
        assert row.status == "error"
        assert row.filename is None
        assert row.error and "connection refused" in row.error


# ── API endpoints ────────────────────────────────────────────────────


def test_run_endpoint_requires_admin(client_factory, regular_user) -> None:
    with client_factory(regular_user) as c:
        response = c.post("/api/backup/run")
    assert response.status_code == 403


def test_list_endpoint_requires_admin(client_factory, regular_user) -> None:
    with client_factory(regular_user) as c:
        response = c.get("/api/backup/list")
    assert response.status_code == 403


def test_run_endpoint_returns_backup_log(
    client_factory, admin_user, session_factory, monkeypatch
) -> None:
    """POST /api/backup/run returns the persisted log row.

    The runner is fully mocked — this verifies the wiring of admin guard,
    runner invocation, log lookup, and Pydantic serialization.
    """
    started_at = datetime(2026, 5, 12, 4, 0, 0, tzinfo=UTC)
    finished_at = datetime(2026, 5, 12, 4, 0, 5, tzinfo=UTC)

    async def fake_run(**kw):
        async with session_factory() as session:
            row = BackupLog(
                started_at=started_at,
                finished_at=finished_at,
                status="success",
                kind="manual",
                filename="weather_2026-05-12_040000.sql.gz",
                size_bytes=12345,
                duration_ms=5000,
                error=None,
            )
            session.add(row)
            await session.commit()
        return backup_runner.BackupResult(
            status="success",
            kind="manual",
            filename="weather_2026-05-12_040000.sql.gz",
            size_bytes=12345,
            duration_ms=5000,
            started_at=started_at,
            finished_at=finished_at,
            error=None,
        )

    # Patch the module attr the endpoint imported via `from app.services.backup
    # import runner; runner.run_backup(...)`.
    monkeypatch.setattr(backup_runner, "run_backup", fake_run)

    with client_factory(admin_user) as c:
        response = c.post("/api/backup/run")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["kind"] == "manual"
    assert body["filename"] == "weather_2026-05-12_040000.sql.gz"
    assert body["size_bytes"] == 12345
    assert body["duration_ms"] == 5000


def test_list_endpoint_returns_remote_archives(
    client_factory, admin_user, monkeypatch
) -> None:
    async def fake_list():
        return [
            backup_runner.RemoteBackup(
                kind="daily",
                name="weather_2026-05-12_040000.sql.gz",
                path="/weather-app-backups/daily/weather_2026-05-12_040000.sql.gz",
                size_bytes=1024,
            ),
            backup_runner.RemoteBackup(
                kind="monthly",
                name="2026-05.sql.gz",
                path="/weather-app-backups/monthly/2026-05.sql.gz",
                size_bytes=2048,
            ),
        ]

    monkeypatch.setattr(backup_runner, "list_remote_backups", fake_list)

    with client_factory(admin_user) as c:
        response = c.get("/api/backup/list")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["total_size_bytes"] == 3072
    names = {row["name"] for row in body["items"]}
    assert names == {"weather_2026-05-12_040000.sql.gz", "2026-05.sql.gz"}


# ── WebDAV PROPFIND parser ──────────────────────────────────────────


def test_propfind_parser_extracts_files_and_skips_parent() -> None:
    xml = """<?xml version="1.0" encoding="utf-8"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/weather-app-backups/daily/</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype><d:collection/></d:resourcetype>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/weather-app-backups/daily/weather_2026-05-12_040000.sql.gz</d:href>
    <d:propstat>
      <d:prop>
        <d:resourcetype/>
        <d:getcontentlength>2048</d:getcontentlength>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>
"""
    rows = _parse_propfind(xml, parent="/weather-app-backups/daily/")
    assert len(rows) == 1
    row = rows[0]
    assert row.name == "weather_2026-05-12_040000.sql.gz"
    assert row.size == 2048
    assert row.is_dir is False
