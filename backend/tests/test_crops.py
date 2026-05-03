from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.models import Crop, User
from app.db.session import get_db
from app.main import app
from app.services import crop as crop_service


def _make_crop(
    id_: int,
    name: str,
    base: float = 10.0,
    opt_min: float | None = None,
    opt_max: float | None = None,
) -> Crop:
    return Crop(
        id=id_,
        name=name,
        base_temperature=base,
        optimal_temp_min=opt_min,
        optimal_temp_max=opt_max,
    )


@pytest.fixture
def client(monkeypatch):
    crops = [
        _make_crop(2, "Огурцы", 15.0, 22.0, 28.0),
        _make_crop(1, "Томаты", 10.0, 18.0, 26.0),
    ]

    async def fake_list(_session):
        return sorted(crops, key=lambda c: c.name)

    monkeypatch.setattr(crop_service, "list_crops", fake_list)

    async def fake_user() -> User:
        return User(id=1, username="admin", password_hash="x")

    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_list_crops_happy_path(client) -> None:
    response = client.get("/api/crops")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    # sorted by name (RU): Огурцы, Томаты
    assert body[0]["name"] == "Огурцы"
    assert body[1]["name"] == "Томаты"
    assert body[0]["base_temperature"] == 15.0
    assert body[0]["optimal_temp_min"] == 22.0
    assert body[0]["optimal_temp_max"] == 28.0
    assert body[1]["id"] == 1


def test_list_crops_requires_auth() -> None:
    app.dependency_overrides.clear()
    with TestClient(app) as c:
        response = c.get("/api/crops")
    assert response.status_code == 401
