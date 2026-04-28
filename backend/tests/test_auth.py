from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services import auth as auth_service


async def _fake_get_db() -> AsyncIterator[None]:
    yield None  # session not used — auth lookup is monkeypatched


def _make_user(password: str = "secret") -> User:
    return User(id=1, username="admin", password_hash=hash_password(password))


@pytest.fixture
def client(monkeypatch):
    user = _make_user("secret")

    async def fake_lookup(_session, username: str):
        return user if username == "admin" else None

    monkeypatch.setattr(auth_service, "get_user_by_username", fake_lookup)
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
