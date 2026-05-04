from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api import auth as auth_module
from app.api.deps import get_current_user, require_admin
from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services import auth as auth_service

_ = get_current_user  # re-export silences unused-import lint


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Per-IP login rate-limit (5/min) leaks across tests — clear it each run."""
    auth_module.limiter.reset()


async def _fake_get_db() -> AsyncIterator[None]:
    yield None  # session not used — auth lookup is monkeypatched


def _make_user(
    *,
    username: str = "admin",
    user_id: int = 1,
    password: str = "secret",
    is_admin: bool = True,
    is_active: bool = True,
) -> User:
    return User(
        id=user_id,
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
    )


def _install_users(monkeypatch, *users: User) -> None:
    by_name = {u.username: u for u in users}

    async def fake_lookup(_session, username: str):
        return by_name.get(username)

    monkeypatch.setattr(auth_service, "get_user_by_username", fake_lookup)


@pytest.fixture
def client(monkeypatch):
    _install_users(monkeypatch, _make_user())
    app.dependency_overrides[get_db] = _fake_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_login_returns_token_pair(client) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert isinstance(body["refresh_token"], str) and body["refresh_token"]


def test_login_wrong_password_returns_401(client) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "admin", "password": "WRONG"}
    )
    assert response.status_code == 401


def test_login_unknown_user_returns_401(client) -> None:
    response = client.post(
        "/api/auth/login", json={"username": "ghost", "password": "x"}
    )
    assert response.status_code == 401


def test_refresh_issues_new_access(client) -> None:
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret"}
    )
    refresh_token = login.json()["refresh_token"]

    response = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_refresh_rejects_access_token(client) -> None:
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret"}
    )
    access_token = login.json()["access_token"]

    response = client.post("/api/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


def test_logout_returns_204(client) -> None:
    response = client.post("/api/auth/logout")
    assert response.status_code == 204


# ── 6.3.0: roles + active checks ────────────────────────────────────────


def test_login_inactive_user_returns_401(monkeypatch) -> None:
    _install_users(
        monkeypatch,
        _make_user(username="frozen", is_admin=False, is_active=False),
    )
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        with TestClient(app) as c:
            response = c.post(
                "/api/auth/login",
                json={"username": "frozen", "password": "secret"},
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "User is inactive"
    finally:
        app.dependency_overrides.clear()


def test_get_current_user_inactive_returns_401(monkeypatch) -> None:
    # User is active at login time, then deactivated; old token must stop working.
    user = _make_user(username="bob", is_admin=False, is_active=True)
    _install_users(monkeypatch, user)
    app.dependency_overrides[get_db] = _fake_get_db
    try:
        with TestClient(app) as c:
            login = c.post(
                "/api/auth/login",
                json={"username": "bob", "password": "secret"},
            )
            token = login.json()["access_token"]
            user.is_active = False  # deactivate after token issuance
            response = c.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
        assert response.status_code == 401
        assert response.json()["detail"] == "User is inactive"
    finally:
        app.dependency_overrides.clear()


def test_me_endpoint_returns_flags(client) -> None:
    login = client.post(
        "/api/auth/login", json={"username": "admin", "password": "secret"}
    )
    token = login.json()["access_token"]
    response = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["is_admin"] is True
    assert body["is_active"] is True


# ── require_admin dependency ─────────────────────────────────────────────


def _admin_probe_app() -> FastAPI:
    """Mount a tiny app exposing a route protected by `require_admin`."""
    probe = FastAPI()

    @probe.get("/admin-only")
    async def admin_only(u: User = Depends(require_admin)) -> dict:
        return {"username": u.username}

    return probe


def test_require_admin_allows_admin(monkeypatch) -> None:
    _install_users(
        monkeypatch,
        _make_user(username="admin", is_admin=True, is_active=True),
    )
    probe = _admin_probe_app()
    probe.dependency_overrides[get_db] = _fake_get_db
    token = create_access_token("admin")

    with TestClient(probe) as c:
        response = c.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"username": "admin"}


def test_require_admin_rejects_non_admin(monkeypatch) -> None:
    _install_users(
        monkeypatch,
        _make_user(username="user", is_admin=False, is_active=True),
    )
    probe = _admin_probe_app()
    probe.dependency_overrides[get_db] = _fake_get_db
    token = create_access_token("user")

    with TestClient(probe) as c:
        response = c.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_require_admin_rejects_unauthenticated() -> None:
    probe = _admin_probe_app()
    probe.dependency_overrides[get_db] = _fake_get_db
    with TestClient(probe) as c:
        response = c.get("/admin-only")
    assert response.status_code == 401
