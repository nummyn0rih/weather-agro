"""Tests for `seed_admin` idempotency.

Replaces `async_session_factory` with an in-memory fake so the script can
run without Postgres. Verifies:
- first run creates an admin with is_admin/is_active = True
- second run is a no-op (no duplicate, no flag mutation, no password change)
- repair path: an existing admin with cleared flags gets is_admin/is_active
  re-enabled but the password hash is NOT touched
"""
from __future__ import annotations

import asyncio
from typing import Iterator

import pytest

from app.core.security import hash_password, verify_password
from app.db.models import User
from app.scripts import seed_admin as seed_admin_module


class _FakeResult:
    def __init__(self, user: User | None) -> None:
        self._user = user

    def scalar_one_or_none(self) -> User | None:
        return self._user


class _FakeSession:
    def __init__(self, store: list[User]) -> None:
        self._store = store
        self.commits = 0

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def execute(self, stmt) -> _FakeResult:  # noqa: ANN001
        # Naive: return the first stored user (script only ever queries by username,
        # and the fake store is single-user).
        user = self._store[0] if self._store else None
        return _FakeResult(user)

    def add(self, user: User) -> None:
        self._store.append(user)

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def fake_session_store(monkeypatch) -> Iterator[list[User]]:
    store: list[User] = []

    def factory():
        return _FakeSession(store)

    monkeypatch.setattr(seed_admin_module, "async_session_factory", factory)
    yield store


def test_seed_admin_creates_then_is_idempotent(fake_session_store, monkeypatch) -> None:
    # Force settings to known values.
    settings = seed_admin_module.get_settings()
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "rootadmin", raising=False)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "supersecret", raising=False)

    asyncio.run(seed_admin_module.seed_admin())
    assert len(fake_session_store) == 1
    user = fake_session_store[0]
    assert user.username == "rootadmin"
    assert user.is_admin is True
    assert user.is_active is True
    original_hash = user.password_hash
    assert verify_password("supersecret", original_hash)

    # Re-seed: must not duplicate, must not change password.
    asyncio.run(seed_admin_module.seed_admin())
    assert len(fake_session_store) == 1
    assert fake_session_store[0].password_hash == original_hash


def test_seed_admin_repairs_cleared_flags(fake_session_store, monkeypatch) -> None:
    settings = seed_admin_module.get_settings()
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "rootadmin", raising=False)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "supersecret", raising=False)

    fake_session_store.append(
        User(
            id=1,
            username="rootadmin",
            password_hash=hash_password("preexisting"),
            is_admin=False,
            is_active=False,
        )
    )

    asyncio.run(seed_admin_module.seed_admin())
    user = fake_session_store[0]
    assert user.is_admin is True
    assert user.is_active is True
    # Password must NOT be reset by the seeder.
    assert verify_password("preexisting", user.password_hash)
