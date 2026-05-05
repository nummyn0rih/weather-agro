"""Tests for admin user-management endpoints (task 6.3.0.2)."""
from __future__ import annotations

from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import auth as auth_module
from app.api.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.db.base import Base
from app.db.models import Invite, User
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    auth_module.limiter.reset()


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sc: Base.metadata.create_all(
                sc, tables=[User.__table__, Invite.__table__]
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def _make_user(
    session_factory, *, username: str, password: str, is_admin: bool, is_active: bool
) -> User:
    async with session_factory() as session:
        user = User(
            username=username,
            password_hash=hash_password(password),
            is_admin=is_admin,
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest_asyncio.fixture
async def admin_user(session_factory) -> User:
    return await _make_user(
        session_factory,
        username="admin@example.com",
        password="adminpass",
        is_admin=True,
        is_active=True,
    )


@pytest_asyncio.fixture
async def second_admin(session_factory) -> User:
    return await _make_user(
        session_factory,
        username="admin2@example.com",
        password="adminpass2",
        is_admin=True,
        is_active=True,
    )


@pytest_asyncio.fixture
async def regular_user(session_factory) -> User:
    return await _make_user(
        session_factory,
        username="bob@example.com",
        password="bobpass",
        is_admin=False,
        is_active=True,
    )


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


# ── GET /api/admin/users ─────────────────────────────────────────────────


def test_admin_lists_users(client_factory, admin_user, regular_user) -> None:
    with client_factory(admin_user) as c:
        response = c.get("/api/admin/users")
    assert response.status_code == 200
    usernames = {row["username"] for row in response.json()}
    assert {admin_user.username, regular_user.username} <= usernames
    sample = response.json()[0]
    for key in ("id", "username", "is_admin", "is_active", "created_at"):
        assert key in sample


def test_non_admin_cannot_list_users(client_factory, regular_user) -> None:
    with client_factory(regular_user) as c:
        response = c.get("/api/admin/users")
    assert response.status_code == 403


def test_anonymous_cannot_list_users(client_factory) -> None:
    with client_factory(None) as c:
        response = c.get("/api/admin/users")
    assert response.status_code == 401


# ── POST /api/admin/users/{id}/reset-password ────────────────────────────


@pytest.mark.asyncio
async def test_reset_password_replaces_hash(
    client_factory, admin_user, regular_user, session_factory
) -> None:
    with client_factory(admin_user) as c:
        response = c.post(
            f"/api/admin/users/{regular_user.id}/reset-password",
            json={"password": "newpass123"},
        )
    assert response.status_code == 200

    async with session_factory() as session:
        fresh = await session.get(User, regular_user.id)
        assert fresh is not None
        assert verify_password("bobpass", fresh.password_hash) is False
        assert verify_password("newpass123", fresh.password_hash) is True


def test_reset_password_short_returns_422(
    client_factory, admin_user, regular_user
) -> None:
    with client_factory(admin_user) as c:
        response = c.post(
            f"/api/admin/users/{regular_user.id}/reset-password",
            json={"password": "short"},
        )
    assert response.status_code == 422


# ── PATCH /api/admin/users/{id} ──────────────────────────────────────────


def test_deactivate_then_reactivate_user(
    client_factory, admin_user, regular_user
) -> None:
    with client_factory(admin_user) as c:
        deact = c.patch(
            f"/api/admin/users/{regular_user.id}", json={"is_active": False}
        )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # Deactivated user cannot log in.
    with client_factory(None) as c:
        login = c.post(
            "/api/auth/login",
            json={"username": regular_user.username, "password": "bobpass"},
        )
    assert login.status_code == 401

    with client_factory(admin_user) as c:
        react = c.patch(
            f"/api/admin/users/{regular_user.id}", json={"is_active": True}
        )
    assert react.status_code == 200
    assert react.json()["is_active"] is True

    with client_factory(None) as c:
        login = c.post(
            "/api/auth/login",
            json={"username": regular_user.username, "password": "bobpass"},
        )
    assert login.status_code == 200


def test_self_demote_returns_400(client_factory, admin_user, second_admin) -> None:
    # second_admin exists so the lockout-guard wouldn't trip first.
    assert second_admin.is_admin
    with client_factory(admin_user) as c:
        response = c.patch(
            f"/api/admin/users/{admin_user.id}", json={"is_admin": False}
        )
    assert response.status_code == 400
    assert "yourself" in response.json()["detail"].lower()


def test_self_deactivate_returns_400(
    client_factory, admin_user, second_admin
) -> None:
    assert second_admin.is_admin
    with client_factory(admin_user) as c:
        response = c.patch(
            f"/api/admin/users/{admin_user.id}", json={"is_active": False}
        )
    assert response.status_code == 400
    assert "yourself" in response.json()["detail"].lower()


def test_demote_other_admin_when_more_than_one_succeeds(
    client_factory, admin_user, second_admin
) -> None:
    """Sanity: demoting one admin while another remains is allowed."""
    with client_factory(second_admin) as c:
        response = c.patch(
            f"/api/admin/users/{admin_user.id}", json={"is_admin": False}
        )
    assert response.status_code == 200
    assert response.json()["is_admin"] is False


@pytest.mark.asyncio
async def test_service_blocks_demoting_last_admin(
    session_factory, admin_user
) -> None:
    """Direct service-level test — guard fires regardless of who the actor is."""
    from fastapi import HTTPException

    from app.services import users as users_service

    async with session_factory() as session:
        # Reload admin_user inside this session.
        target = await session.get(User, admin_user.id)
        assert target is not None and target.is_admin and target.is_active
        # Make a *different* admin act, but flip them inactive so admin_user
        # is in fact the last active admin.
        other = User(
            username="other-admin@example.com",
            password_hash=hash_password("x"),
            is_admin=True,
            is_active=False,
        )
        session.add(other)
        await session.commit()
        await session.refresh(other)

        with pytest.raises(HTTPException) as exc:
            await users_service.update_user(
                session,
                user_id=target.id,
                is_admin=False,
                is_active=None,
                actor=other,
            )
        assert exc.value.status_code == 400
        assert "last active admin" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_service_blocks_deactivating_last_admin(
    session_factory, admin_user
) -> None:
    from fastapi import HTTPException

    from app.services import users as users_service

    async with session_factory() as session:
        target = await session.get(User, admin_user.id)
        assert target is not None
        other = User(
            username="ghost-admin@example.com",
            password_hash=hash_password("x"),
            is_admin=True,
            is_active=False,
        )
        session.add(other)
        await session.commit()
        await session.refresh(other)

        with pytest.raises(HTTPException) as exc:
            await users_service.update_user(
                session,
                user_id=target.id,
                is_admin=None,
                is_active=False,
                actor=other,
            )
        assert exc.value.status_code == 400
        assert "last active admin" in exc.value.detail.lower()


def test_non_admin_cannot_patch_user(
    client_factory, admin_user, regular_user
) -> None:
    with client_factory(regular_user) as c:
        response = c.patch(
            f"/api/admin/users/{admin_user.id}", json={"is_active": False}
        )
    assert response.status_code == 403


def test_patch_unknown_user_returns_404(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        response = c.patch("/api/admin/users/99999", json={"is_active": False})
    assert response.status_code == 404
