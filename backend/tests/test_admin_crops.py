"""Tests for admin crops CRUD endpoints (task 6.3.2).

Uses an isolated SQLite fixture with PRAGMA foreign_keys=ON. JSONB columns
on FieldEvent are rendered as plain JSON via a @compiles hook.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.api.deps import get_current_user
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import Crop, FieldEvent, Location, LocationCrop, User
from app.db.session import get_db
from app.main import app


@compiles(JSONB, "sqlite")
def _jsonb_to_sqlite_json(_element, _compiler, **_kw):
    return "JSON"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # field_events.photos uses Postgres-specific `'[]'::jsonb` server_default
    # — strip around DDL so SQLite doesn't choke on the cast literal.
    photos_col = FieldEvent.__table__.c.photos
    saved_default = photos_col.server_default
    photos_col.server_default = None
    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sc: Base.metadata.create_all(
                    sc,
                    tables=[
                        User.__table__,
                        Crop.__table__,
                        Location.__table__,
                        LocationCrop.__table__,
                        FieldEvent.__table__,
                    ],
                )
            )
    finally:
        photos_col.server_default = saved_default
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _make_user(
    session_factory, *, username: str, is_admin: bool
) -> User:
    async with session_factory() as session:
        user = User(
            username=username,
            password_hash=hash_password("x"),
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


def _crop_payload(**overrides) -> dict:
    base = {
        "name": "Томаты",
        "base_temperature": 10.0,
        "optimal_temp_min": 18.0,
        "optimal_temp_max": 26.0,
    }
    base.update(overrides)
    return base


# ── POST /api/crops ──────────────────────────────────────────────────────


def test_create_crop_happy_path(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        resp = c.post("/api/crops", json=_crop_payload())
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] > 0
    assert body["name"] == "Томаты"
    assert body["base_temperature"] == 10.0
    assert body["optimal_temp_min"] == 18.0
    assert body["optimal_temp_max"] == 26.0


def test_create_crop_duplicate_name_returns_409(
    client_factory, admin_user
) -> None:
    with client_factory(admin_user) as c:
        first = c.post("/api/crops", json=_crop_payload())
        second = c.post("/api/crops", json=_crop_payload())
    assert first.status_code == 201
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"].lower()


def test_create_crop_forbidden_for_regular_user(
    client_factory, regular_user
) -> None:
    with client_factory(regular_user) as c:
        resp = c.post("/api/crops", json=_crop_payload())
    assert resp.status_code == 403


def test_create_crop_unauthorized(client_factory) -> None:
    with client_factory(None) as c:
        resp = c.post("/api/crops", json=_crop_payload())
    assert resp.status_code == 401


# ── PUT /api/crops/{id} ──────────────────────────────────────────────────


def test_put_crop_happy_path(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        created = c.post("/api/crops", json=_crop_payload())
        crop_id = created.json()["id"]
        resp = c.put(
            f"/api/crops/{crop_id}",
            json={"base_temperature": 12.5},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["base_temperature"] == 12.5
    assert body["name"] == "Томаты"  # unchanged


def test_put_crop_not_found(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        resp = c.put("/api/crops/9999", json={"base_temperature": 5.0})
    assert resp.status_code == 404


def test_put_crop_duplicate_name_returns_409(
    client_factory, admin_user
) -> None:
    with client_factory(admin_user) as c:
        a = c.post("/api/crops", json=_crop_payload(name="Огурцы")).json()
        b = c.post("/api/crops", json=_crop_payload(name="Томаты")).json()
        resp = c.put(f"/api/crops/{b['id']}", json={"name": "Огурцы"})
        assert a  # silence linter
    assert resp.status_code == 409


def test_put_crop_forbidden_for_regular_user(
    client_factory, admin_user, regular_user
) -> None:
    with client_factory(admin_user) as c:
        crop_id = c.post("/api/crops", json=_crop_payload()).json()["id"]
    with client_factory(regular_user) as c:
        resp = c.put(f"/api/crops/{crop_id}", json={"base_temperature": 5.0})
    assert resp.status_code == 403


# ── DELETE /api/crops/{id} ───────────────────────────────────────────────


def test_delete_crop_happy_path(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        crop_id = c.post("/api/crops", json=_crop_payload()).json()["id"]
        resp = c.delete(f"/api/crops/{crop_id}")
    assert resp.status_code == 204
    with client_factory(admin_user) as c:
        again = c.delete(f"/api/crops/{crop_id}")
    assert again.status_code == 404


def test_delete_crop_not_found(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        resp = c.delete("/api/crops/9999")
    assert resp.status_code == 404


def test_delete_crop_forbidden_for_regular_user(
    client_factory, admin_user, regular_user
) -> None:
    with client_factory(admin_user) as c:
        crop_id = c.post("/api/crops", json=_crop_payload()).json()["id"]
    with client_factory(regular_user) as c:
        resp = c.delete(f"/api/crops/{crop_id}")
    assert resp.status_code == 403


async def test_delete_crop_with_field_events_returns_409(
    client_factory, admin_user, session_factory
) -> None:
    with client_factory(admin_user) as c:
        crop_id = c.post("/api/crops", json=_crop_payload()).json()["id"]

    async with session_factory() as session:
        loc = Location(
            name="Field A",
            latitude=45.0,
            longitude=39.0,
            type="own",
            import_status="done",
            import_progress=100,
        )
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        session.add(
            FieldEvent(
                location_id=loc.id,
                event_type="planting",
                event_date=date(2026, 4, 1),
                crop_id=crop_id,
                photos=[],
            )
        )
        await session.commit()

    with client_factory(admin_user) as c:
        resp = c.delete(f"/api/crops/{crop_id}")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "referenced" in detail["message"].lower()
    assert detail["references"]["field_events"] == 1
    assert detail["references"]["location_crops"] == 0


async def test_delete_crop_with_location_crops_returns_409(
    client_factory, admin_user, session_factory
) -> None:
    with client_factory(admin_user) as c:
        crop_id = c.post("/api/crops", json=_crop_payload()).json()["id"]

    async with session_factory() as session:
        loc = Location(
            name="Field B",
            latitude=46.0,
            longitude=40.0,
            type="own",
            import_status="done",
            import_progress=100,
        )
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        session.add(
            LocationCrop(
                location_id=loc.id,
                crop_id=crop_id,
                season_year=2026,
            )
        )
        await session.commit()

    with client_factory(admin_user) as c:
        resp = c.delete(f"/api/crops/{crop_id}")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "referenced" in detail["message"].lower()
    assert detail["references"]["location_crops"] == 1
    assert detail["references"]["field_events"] == 0
