"""Tests for the Settings API (task 6.3).

Uses an aiosqlite in-memory engine with a JSONB→JSON compile shim — mirrors
the pattern used in ``tests/test_admin_crops.py``. Covers ADR-002 DoD:
masking, sentinel PUT, env→DB fallback, resolver precedence, and admin gate.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.encryption import reset_cache as reset_encryption_cache
from app.db.base import Base
from app.db.models import Setting, User
from app.db.session import get_db
from app.main import app
from app.services.settings import resolver as settings_resolver
from app.services.settings.store import load_raw


@compiles(JSONB, "sqlite")
def _jsonb_to_sqlite_json(_element, _compiler, **_kw):
    return "JSON"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sc: Base.metadata.create_all(
                sc, tables=[User.__table__, Setting.__table__]
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _make_user(session_factory, *, username: str, is_admin: bool) -> User:
    async with session_factory() as session:
        user = User(
            username=username,
            password_hash="x",
            is_admin=is_admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def admin_user(session_factory) -> User:
    return await _make_user(session_factory, username="admin@x", is_admin=True)


@pytest_asyncio.fixture
async def regular_user(session_factory) -> User:
    return await _make_user(session_factory, username="bob@x", is_admin=False)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch) -> None:
    """Wipe env for every test — each one opts in to specific overrides."""
    cfg = get_settings()
    monkeypatch.setattr(cfg, "OPENWEATHERMAP_API_KEY", "")
    monkeypatch.setattr(cfg, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(cfg, "YANDEX_DISK_LOGIN", "")
    monkeypatch.setattr(cfg, "YANDEX_DISK_APP_PASSWORD", "")
    monkeypatch.setattr(cfg, "YANDEX_DISK_BACKUP_PATH", "/weather-app-backups/")
    monkeypatch.setattr(cfg, "BACKUP_RETENTION_DAILY", 30)
    monkeypatch.setattr(cfg, "BACKUP_RETENTION_MONTHLY", 12)
    monkeypatch.setattr(cfg, "SECRET_KEY", "x" * 64)
    reset_encryption_cache()
    yield
    reset_encryption_cache()


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


# ── /sources ─────────────────────────────────────────────────────────────────


def test_sources_get_returns_defaults_when_unset(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        resp = c.get("/api/settings/sources")
    assert resp.status_code == 200
    body = resp.json()
    assert body["priority"] == ["open_meteo", "nasa_power", "openweathermap"]
    assert body["enabled"]["open_meteo"] is True
    assert body["enabled"]["openweathermap"] is False
    assert body["average_mode"] is False


def test_sources_put_then_get_roundtrip(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        put_resp = c.put(
            "/api/settings/sources",
            json={
                "priority": ["nasa_power", "open_meteo", "openweathermap"],
                "average_mode": True,
            },
        )
        get_resp = c.get("/api/settings/sources")
    assert put_resp.status_code == 200
    body = get_resp.json()
    assert body["priority"] == ["nasa_power", "open_meteo", "openweathermap"]
    assert body["average_mode"] is True


# ── /api-keys ────────────────────────────────────────────────────────────────


def test_api_keys_put_then_get_masks_secret(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        c.put(
            "/api/settings/api-keys",
            json={"openweathermap_api_key": "abcdef1234"},
        )
        resp = c.get("/api/settings/api-keys")
    assert resp.status_code == 200
    assert resp.json()["openweathermap_api_key"] == "***1234"


def test_api_keys_put_with_masked_value_is_noop(
    client_factory, admin_user, session_factory
) -> None:
    with client_factory(admin_user) as c:
        c.put(
            "/api/settings/api-keys",
            json={"openweathermap_api_key": "abcdef1234"},
        )

    import asyncio

    async def _read():
        async with session_factory() as session:
            return await load_raw(session, "api_keys")

    before = asyncio.run(_read())

    with client_factory(admin_user) as c:
        c.put(
            "/api/settings/api-keys",
            json={"openweathermap_api_key": "***1234"},
        )

    after = asyncio.run(_read())
    assert before == after


def test_api_keys_put_empty_string_clears_and_falls_back_to_env(
    client_factory, admin_user, monkeypatch
) -> None:
    with client_factory(admin_user) as c:
        c.put(
            "/api/settings/api-keys",
            json={"openweathermap_api_key": "abcdef1234"},
        )
        get_before = c.get("/api/settings/api-keys").json()
        assert get_before["openweathermap_api_key"] == "***1234"

        cfg = get_settings()
        monkeypatch.setattr(cfg, "OPENWEATHERMAP_API_KEY", "envkey5678")

        c.put(
            "/api/settings/api-keys",
            json={"openweathermap_api_key": ""},
        )
        get_after = c.get("/api/settings/api-keys").json()
    assert get_after["openweathermap_api_key"] == "***5678"


# ── /telegram ────────────────────────────────────────────────────────────────


def test_telegram_put_then_get_masks_token(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        c.put("/api/settings/telegram", json={"bot_token": "bot1:ABCDXYZ9999"})
        resp = c.get("/api/settings/telegram")
    assert resp.json()["bot_token"] == "***9999"


# ── /backup ──────────────────────────────────────────────────────────────────


def test_backup_full_roundtrip(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        put_resp = c.put(
            "/api/settings/backup",
            json={
                "yandex_disk_login": "ops@example.com",
                "yandex_disk_app_password": "secretpass4321",
                "yandex_disk_path": "/backups/agro/",
                "retention_daily": 45,
                "retention_monthly": 18,
            },
        )
        get_resp = c.get("/api/settings/backup")
    assert put_resp.status_code == 200
    body = get_resp.json()
    assert body["yandex_disk_login"] == "ops@example.com"
    assert body["yandex_disk_app_password"] == "***4321"
    assert body["yandex_disk_path"] == "/backups/agro/"
    assert body["retention_daily"] == 45
    assert body["retention_monthly"] == 18


# ── Auth gates ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "endpoint,payload",
    [
        ("/api/settings/sources", {"average_mode": True}),
        ("/api/settings/api-keys", {"openweathermap_api_key": "x"}),
        ("/api/settings/telegram", {"bot_token": "x"}),
        ("/api/settings/backup", {"yandex_disk_login": "x"}),
    ],
)
def test_put_forbidden_for_non_admin(
    client_factory, regular_user, endpoint, payload
) -> None:
    with client_factory(regular_user) as c:
        resp = c.put(endpoint, json=payload)
    assert resp.status_code == 403


def test_put_unauthorized(client_factory) -> None:
    with client_factory(None) as c:
        resp = c.put(
            "/api/settings/api-keys",
            json={"openweathermap_api_key": "x"},
        )
    assert resp.status_code == 401


# ── Resolver ────────────────────────────────────────────────────────────────


async def test_resolver_db_overrides_env(
    session_factory, admin_user, monkeypatch
) -> None:
    cfg = get_settings()
    monkeypatch.setattr(cfg, "OPENWEATHERMAP_API_KEY", "env-key")

    async with session_factory() as session:
        from app.core.encryption import encrypt
        from app.services.settings.store import save_raw

        await save_raw(
            session, "api_keys", {"openweathermap_api_key": encrypt("db-key")}
        )
        await session.commit()

    async with session_factory() as session:
        value = await settings_resolver.get_secret(
            "openweathermap_api_key", session=session
        )
    assert value == "db-key"


async def test_resolver_env_fallback_when_no_db_row(
    session_factory, monkeypatch
) -> None:
    cfg = get_settings()
    monkeypatch.setattr(cfg, "OPENWEATHERMAP_API_KEY", "env-only")
    async with session_factory() as session:
        value = await settings_resolver.get_secret(
            "openweathermap_api_key", session=session
        )
    assert value == "env-only"


async def test_resolver_returns_none_when_neither_set(session_factory) -> None:
    async with session_factory() as session:
        value = await settings_resolver.get_secret(
            "openweathermap_api_key", session=session
        )
    assert value is None
