"""Tests for the invite system (task 6.3.0.1).

Use an in-memory SQLite engine to back the real `get_db` dependency, in
the same style as `test_alert_history_api.test_date_to_is_inclusive_end_of_day`.
This exercises the full SQLAlchemy + service path end-to-end through the
real API routes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import auth as auth_module
from app.api.deps import get_current_user
from app.core.security import hash_password
from app.db.base import Base
from app.db.models import Invite, User
from app.db.session import get_db
from app.main import app


# ── Fixtures ─────────────────────────────────────────────────────────────


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
    """Return a builder that yields a TestClient acting as the given user (or anon)."""

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


# ── POST /api/admin/invites ──────────────────────────────────────────────


def test_admin_creates_invite(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        response = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token"]
    assert body["invite_url"].endswith(f"/accept-invite?token={body['token']}")
    assert body["username"] == "alice@example.com"
    assert body["is_admin"] is False
    assert body["expires_at"]


def test_non_admin_cannot_create_invite(client_factory, regular_user) -> None:
    with client_factory(regular_user) as c:
        response = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        )
    assert response.status_code == 403


def test_create_invite_for_existing_username_returns_409(
    client_factory, admin_user
) -> None:
    with client_factory(admin_user) as c:
        response = c.post(
            "/api/admin/invites",
            json={"username": admin_user.username, "is_admin": False},
        )
    assert response.status_code == 409


def test_duplicate_pending_invite_returns_409(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        first = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        )
        assert first.status_code == 201
        second = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        )
    assert second.status_code == 409


# ── GET /api/auth/invites/{token} ────────────────────────────────────────


def test_public_lookup_returns_invite(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        token = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": True},
        ).json()["token"]

    with client_factory(None) as c:
        response = c.get(f"/api/auth/invites/{token}")
    assert response.status_code == 200
    assert response.json() == {"username": "alice@example.com", "is_admin": True}


def test_public_lookup_unknown_token_returns_404(client_factory) -> None:
    with client_factory(None) as c:
        response = c.get("/api/auth/invites/does-not-exist")
    assert response.status_code == 404


def test_public_lookup_revoked_returns_410(
    client_factory, admin_user, session_factory
) -> None:
    with client_factory(admin_user) as c:
        created = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        ).json()
        revoke = c.delete(f"/api/admin/invites/{created['id']}")
        assert revoke.status_code == 204

    with client_factory(None) as c:
        response = c.get(f"/api/auth/invites/{created['token']}")
    assert response.status_code == 410


@pytest.mark.asyncio
async def test_public_lookup_expired_returns_410(
    client_factory, admin_user, session_factory
) -> None:
    with client_factory(admin_user) as c:
        created = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        ).json()

    # Roll expires_at into the past directly in the DB.
    async with session_factory() as session:
        invite = await session.get(Invite, created["id"])
        assert invite is not None
        invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    with client_factory(None) as c:
        response = c.get(f"/api/auth/invites/{created['token']}")
    assert response.status_code == 410


# ── POST /api/auth/invites/{token}/accept ────────────────────────────────


def test_accept_creates_user_and_returns_tokens(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        token = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        ).json()["token"]

    with client_factory(None) as c:
        response = c.post(
            f"/api/auth/invites/{token}/accept",
            json={"password": "alicepass"},
        )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_accept_twice_second_call_returns_410(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        token = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        ).json()["token"]

    with client_factory(None) as c:
        first = c.post(
            f"/api/auth/invites/{token}/accept", json={"password": "alicepass"}
        )
        assert first.status_code == 200
        second = c.post(
            f"/api/auth/invites/{token}/accept", json={"password": "alicepass"}
        )
    assert second.status_code == 410


def test_accept_short_password_returns_422(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        token = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        ).json()["token"]

    with client_factory(None) as c:
        response = c.post(
            f"/api/auth/invites/{token}/accept", json={"password": "short"}
        )
    assert response.status_code == 422


# ── DELETE /api/admin/invites/{id} ───────────────────────────────────────


def test_revoke_pending_invite_returns_204(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        created = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        ).json()
        response = c.delete(f"/api/admin/invites/{created['id']}")
    assert response.status_code == 204

    with client_factory(None) as c:
        lookup = c.get(f"/api/auth/invites/{created['token']}")
    assert lookup.status_code == 410


def test_revoke_accepted_invite_returns_404(client_factory, admin_user) -> None:
    with client_factory(admin_user) as c:
        created = c.post(
            "/api/admin/invites",
            json={"username": "alice@example.com", "is_admin": False},
        ).json()

    with client_factory(None) as c:
        accept = c.post(
            f"/api/auth/invites/{created['token']}/accept",
            json={"password": "alicepass"},
        )
        assert accept.status_code == 200

    with client_factory(admin_user) as c:
        response = c.delete(f"/api/admin/invites/{created['id']}")
    assert response.status_code == 404


# ── GET /api/admin/invites ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_returns_all_statuses(
    client_factory, admin_user, session_factory
) -> None:
    with client_factory(admin_user) as c:
        pending = c.post(
            "/api/admin/invites",
            json={"username": "pending@example.com", "is_admin": False},
        ).json()
        revoked = c.post(
            "/api/admin/invites",
            json={"username": "revoked@example.com", "is_admin": False},
        ).json()
        c.delete(f"/api/admin/invites/{revoked['id']}")
        accepted = c.post(
            "/api/admin/invites",
            json={"username": "accepted@example.com", "is_admin": False},
        ).json()
        expired = c.post(
            "/api/admin/invites",
            json={"username": "expired@example.com", "is_admin": False},
        ).json()

    with client_factory(None) as c:
        c.post(
            f"/api/auth/invites/{accepted['token']}/accept",
            json={"password": "longpass1"},
        )

    async with session_factory() as session:
        invite = await session.get(Invite, expired["id"])
        assert invite is not None
        invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    with client_factory(admin_user) as c:
        response = c.get("/api/admin/invites")
    assert response.status_code == 200
    by_username = {row["username"]: row for row in response.json()}
    assert by_username["pending@example.com"]["status"] == "pending"
    assert by_username["revoked@example.com"]["status"] == "revoked"
    assert by_username["accepted@example.com"]["status"] == "accepted"
    assert by_username["expired@example.com"]["status"] == "expired"
    # Token must NOT leak in the list.
    for row in response.json():
        assert "token" not in row
