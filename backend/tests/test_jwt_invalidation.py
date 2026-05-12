"""JWT invalidation tests (task 6.3.0-DEBT.2).

Verifies that:
  1. Changing one's own password invalidates the old refresh token (401 on /refresh).
  2. Admin-deactivating a user invalidates old access tokens (401 on protected endpoint).
  3. Re-activating a deactivated user — newly minted tokens work end-to-end.

All tests go through the real auth chain (Bearer tokens, no get_current_user
override), so the iat-vs-tokens_invalidated_at check is exercised end-to-end.
"""
from __future__ import annotations

import time
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import auth as auth_module
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import Invite, User
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Per-IP login rate-limit (5/min) leaks across tests — clear it each run."""
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
    session_factory,
    *,
    username: str,
    password: str,
    is_admin: bool = False,
) -> User:
    async with session_factory() as session:
        user = User(
            username=username,
            password_hash=hash_password(password),
            is_admin=is_admin,
            is_active=True,
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
    )


@pytest_asyncio.fixture
async def regular_user(session_factory) -> User:
    return await _make_user(
        session_factory,
        username="bob@example.com",
        password="bobpass",
    )


@pytest.fixture
def client(session_factory):
    """Client that uses the real auth chain — no get_current_user override."""

    async def fake_get_db() -> AsyncIterator:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = fake_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(c: TestClient, username: str, password: str) -> dict:
    response = c.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_password_change_invalidates_old_refresh_token(
    client: TestClient, regular_user: User
) -> None:
    tokens = _login(client, regular_user.username, "bobpass")
    old_access = tokens["access_token"]
    old_refresh = tokens["refresh_token"]

    change = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {old_access}"},
        json={"old_password": "bobpass", "new_password": "newbobpass"},
    )
    assert change.status_code == 204, change.text

    refresh = client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert refresh.status_code == 401
    assert refresh.json()["detail"] == "Token invalidated"

    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {old_access}"}
    )
    assert me.status_code == 401


def test_admin_deactivation_invalidates_old_access_token(
    client: TestClient, admin_user: User, regular_user: User
) -> None:
    bob_tokens = _login(client, regular_user.username, "bobpass")
    bob_access = bob_tokens["access_token"]

    me_before = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {bob_access}"}
    )
    assert me_before.status_code == 200

    admin_tokens = _login(client, admin_user.username, "adminpass")
    admin_access = admin_tokens["access_token"]

    deact = client.patch(
        f"/api/admin/users/{regular_user.id}",
        headers={"Authorization": f"Bearer {admin_access}"},
        json={"is_active": False},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["is_active"] is False

    me_after = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {bob_access}"}
    )
    assert me_after.status_code == 401
    # `is_active` check fires before the iat check; both would block this token.
    assert me_after.json()["detail"] in {"User is inactive", "Token invalidated"}


def test_reactivation_issues_working_tokens(
    client: TestClient, admin_user: User, regular_user: User
) -> None:
    admin_tokens = _login(client, admin_user.username, "adminpass")
    admin_access = admin_tokens["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_access}"}

    deact = client.patch(
        f"/api/admin/users/{regular_user.id}",
        headers=admin_headers,
        json={"is_active": False},
    )
    assert deact.status_code == 200

    react = client.patch(
        f"/api/admin/users/{regular_user.id}",
        headers=admin_headers,
        json={"is_active": True},
    )
    assert react.status_code == 200

    # JWT iat is second-granular; wait past the invalidation second so the
    # next login's iat clears `int(iat) <= int(tokens_invalidated_at)`.
    time.sleep(1.1)

    tokens = _login(client, regular_user.username, "bobpass")
    new_access = tokens["access_token"]

    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {new_access}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == regular_user.username

    new_refresh = tokens["refresh_token"]
    refresh = client.post(
        "/api/auth/refresh", json={"refresh_token": new_refresh}
    )
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]
