from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_module
from app.core.security import hash_password
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services import auth as auth_service


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Per-IP login rate-limit (5/min) leaks across tests — clear it each run."""
    auth_module.limiter.reset()


class _FakeSession:
    """Minimal async-session stub: change-password only calls add() + commit()."""

    def add(self, _obj: object) -> None:
        return None

    async def commit(self) -> None:
        return None


async def _fake_get_db() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _make_user(
    *,
    username: str = "bob",
    user_id: int = 1,
    password: str = "old-password",
    is_admin: bool = False,
    is_active: bool = True,
) -> User:
    return User(
        id=user_id,
        username=username,
        password_hash=hash_password(password),
        is_admin=is_admin,
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


def _install_users(monkeypatch, *users: User) -> None:
    by_name = {u.username: u for u in users}

    async def fake_lookup(_session, username: str):
        return by_name.get(username)

    monkeypatch.setattr(auth_service, "get_user_by_username", fake_lookup)


@pytest.fixture
def user() -> User:
    return _make_user()


@pytest.fixture
def client(monkeypatch, user: User):
    _install_users(monkeypatch, user)
    app.dependency_overrides[get_db] = _fake_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _login(c: TestClient, username: str, password: str):
    return c.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


def _access_token(c: TestClient, username: str, password: str) -> str:
    response = _login(c, username, password)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_change_password_happy_path(client: TestClient) -> None:
    token = _access_token(client, "bob", "old-password")

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "old-password", "new_password": "new-strong-pw"},
    )
    assert response.status_code == 204
    assert response.content == b""

    # old credentials no longer authenticate
    old_login = _login(client, "bob", "old-password")
    assert old_login.status_code == 401

    # new credentials work
    new_login = _login(client, "bob", "new-strong-pw")
    assert new_login.status_code == 200
    assert new_login.json()["access_token"]


def test_change_password_wrong_old(client: TestClient) -> None:
    token = _access_token(client, "bob", "old-password")

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "WRONG", "new_password": "new-strong-pw"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Incorrect old password"

    # password unchanged — old still works
    assert _login(client, "bob", "old-password").status_code == 200


def test_change_password_too_short(client: TestClient) -> None:
    token = _access_token(client, "bob", "old-password")

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "old-password", "new_password": "1234567"},
    )
    assert response.status_code == 422

    assert _login(client, "bob", "old-password").status_code == 200


def test_change_password_same_as_old(client: TestClient) -> None:
    token = _access_token(client, "bob", "old-password")

    response = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"old_password": "old-password", "new_password": "old-password"},
    )
    assert response.status_code == 422
    body = response.json()
    assert "must differ" in str(body).lower()

    assert _login(client, "bob", "old-password").status_code == 200


def test_change_password_unauthorized(client: TestClient) -> None:
    response = client.post(
        "/api/auth/change-password",
        json={"old_password": "old-password", "new_password": "new-strong-pw"},
    )
    assert response.status_code == 401
