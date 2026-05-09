"""Role-level sweep for admin-only endpoints (task 6.3.0.3).

For every endpoint classified as **admin** in `docs/endpoint-roles.md`, this
suite verifies:

* anonymous request → 401
* authenticated non-admin → 403
* authenticated admin → not 401/403 (i.e. role gate passed)

The third case does not assert 2xx: many of these routes need fixtures
(existing rows, request bodies) to reach a true happy path. That is covered
by the per-feature test modules (`test_locations.py`, `test_alert_rules.py`,
`test_admin_users.py`, `test_invites.py`). What's verified here is that the
role check itself does not block admin traffic — i.e. status is anything
other than 401/403.
"""
from __future__ import annotations

from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.main import app


# (method, path, request_kwargs)
ADMIN_ONLY_ENDPOINTS: list[tuple[str, str, dict]] = [
    # locations — shared resource mutations
    (
        "POST",
        "/api/locations",
        {
            "json": {
                "name": "Sweep",
                "latitude": 45.0,
                "longitude": 39.0,
                "type": "own",
            }
        },
    ),
    ("PUT", "/api/locations/1", {"json": {"note": "x"}}),
    ("DELETE", "/api/locations/1", {}),
    # alert rules — system-wide
    (
        "POST",
        "/api/alerts/rules",
        {
            "json": {
                "name": "Sweep",
                "parameter": "temperature_max",
                "condition": "gt",
                "threshold": 30.0,
            }
        },
    ),
    ("PUT", "/api/alerts/rules/1", {"json": {"enabled": False}}),
    ("DELETE", "/api/alerts/rules/1", {}),
    # admin/users
    ("GET", "/api/admin/users", {}),
    ("GET", "/api/admin/users/1", {}),
    ("PATCH", "/api/admin/users/1", {"json": {"is_active": False}}),
    (
        "POST",
        "/api/admin/users/1/reset-password",
        {"json": {"password": "newpass123"}},
    ),
    # admin/invites
    (
        "POST",
        "/api/admin/invites",
        {"json": {"username": "new@example.com", "is_admin": False}},
    ),
    ("GET", "/api/admin/invites", {}),
    ("DELETE", "/api/admin/invites/1", {}),
]


_IDS = [f"{m} {p}" for m, p, _ in ADMIN_ONLY_ENDPOINTS]


@pytest.fixture
def regular_user() -> User:
    return User(
        id=42,
        username="bob@example.com",
        password_hash="x",
        is_admin=False,
        is_active=True,
    )


@pytest.fixture
def admin_user() -> User:
    return User(
        id=1,
        username="admin@example.com",
        password_hash="x",
        is_admin=True,
        is_active=True,
    )


@pytest.fixture
def stub_db():
    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_db] = fake_db
    yield
    app.dependency_overrides.pop(get_db, None)


def _override_user(user: User | None) -> None:
    if user is None:
        app.dependency_overrides.pop(get_current_user, None)
        return

    async def fake() -> User:
        return user

    app.dependency_overrides[get_current_user] = fake


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path,kwargs", ADMIN_ONLY_ENDPOINTS, ids=_IDS)
def test_admin_only_anonymous_returns_401(
    method: str, path: str, kwargs: dict, stub_db
) -> None:
    _override_user(None)
    with TestClient(app) as c:
        response = c.request(method, path, **kwargs)
    assert response.status_code == 401, (
        f"{method} {path} expected 401 for anonymous, got {response.status_code}"
    )


@pytest.mark.parametrize("method,path,kwargs", ADMIN_ONLY_ENDPOINTS, ids=_IDS)
def test_admin_only_user_returns_403(
    method: str, path: str, kwargs: dict, regular_user: User, stub_db
) -> None:
    _override_user(regular_user)
    with TestClient(app) as c:
        response = c.request(method, path, **kwargs)
    assert response.status_code == 403, (
        f"{method} {path} expected 403 for non-admin, got "
        f"{response.status_code}: {response.text}"
    )


@pytest.mark.parametrize("method,path,kwargs", ADMIN_ONLY_ENDPOINTS, ids=_IDS)
def test_admin_only_admin_passes_role_gate(
    method: str, path: str, kwargs: dict, admin_user: User, stub_db
) -> None:
    """Admin must clear 401/403. The ultimate status (200/204/404/422/500)
    depends on whether the underlying service can resolve the request without
    a real DB; we only assert the role gate did not reject the call.
    """
    _override_user(admin_user)
    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.request(method, path, **kwargs)
    assert response.status_code not in (401, 403), (
        f"{method} {path} role gate blocked admin: {response.status_code} "
        f"{response.text}"
    )
