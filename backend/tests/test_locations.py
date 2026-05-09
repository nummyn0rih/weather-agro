from datetime import datetime, timezone
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api import locations as locations_api
from app.api.deps import get_current_user
from app.db.models import Location, User
from app.db.session import get_db
from app.main import app
from app.services import location as location_service

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _make_loc(
    id_: int = 1,
    name: str = "Field A",
    region: str | None = "South",
    type_: str = "own",
) -> Location:
    return Location(
        id=id_,
        name=name,
        latitude=45.0,
        longitude=39.0,
        region=region,
        type=type_,
        note=None,
        created_at=_NOW,
        import_status="pending",
        import_progress=0,
    )


@pytest.fixture
def client(monkeypatch):
    store: dict[int, Location] = {1: _make_loc()}

    async def fake_list(_session, region=None, type_=None):
        items = list(store.values())
        if region:
            items = [loc for loc in items if loc.region == region]
        if type_:
            items = [loc for loc in items if loc.type == type_]
        return items

    async def fake_get(_session, lid):
        return store.get(lid)

    async def fake_create(_session, data):
        new_id = max(store.keys(), default=0) + 1
        loc = Location(
            id=new_id,
            created_at=_NOW,
            import_status="pending",
            import_progress=0,
            **data.model_dump(),
        )
        store[new_id] = loc
        return loc

    async def fake_update(_session, lid, data):
        if lid not in store:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(store[lid], k, v)
        return store[lid]

    async def fake_delete(_session, lid):
        return store.pop(lid, None) is not None

    async def fake_status(_session, lid):
        loc = store.get(lid)
        if loc is None:
            return None
        from app.schemas.location import LocationImportStatus

        return LocationImportStatus(
            location_id=loc.id,
            status=loc.import_status,
            progress=loc.import_progress,
            started_at=loc.import_started_at,
            finished_at=loc.import_finished_at,
            error=loc.import_error,
        )

    monkeypatch.setattr(location_service, "list_locations", fake_list)
    monkeypatch.setattr(location_service, "get_location", fake_get)
    monkeypatch.setattr(location_service, "create_location", fake_create)
    monkeypatch.setattr(location_service, "update_location", fake_update)
    monkeypatch.setattr(location_service, "delete_location", fake_delete)
    monkeypatch.setattr(location_service, "get_import_status", fake_status)

    async def noop_backfill(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        locations_api.backfill_service, "run_backfill", noop_backfill
    )

    async def fake_user() -> User:
        return User(
            id=1,
            username="admin",
            password_hash="x",
            is_admin=True,
            is_active=True,
        )

    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_list_returns_seed(client) -> None:
    response = client.get("/api/locations")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Field A"


def test_list_filter_by_region(client) -> None:
    assert len(client.get("/api/locations?region=South").json()) == 1
    assert len(client.get("/api/locations?region=Center").json()) == 0


def test_list_filter_by_type(client) -> None:
    assert len(client.get("/api/locations?type=own").json()) == 1
    assert len(client.get("/api/locations?type=purchase").json()) == 0


def test_get_location(client) -> None:
    response = client.get("/api/locations/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_location_404(client) -> None:
    assert client.get("/api/locations/999").status_code == 404


def test_create_location(client) -> None:
    response = client.post(
        "/api/locations",
        json={
            "name": "Field B",
            "latitude": 50.0,
            "longitude": 40.0,
            "region": "Center",
            "type": "own",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Field B"
    assert body["id"] == 2
    assert body["import_status"] == "pending"
    assert body["import_progress"] == 0


def test_import_status_endpoint(client) -> None:
    response = client.get("/api/locations/1/import-status")
    assert response.status_code == 200
    body = response.json()
    assert body["location_id"] == 1
    assert body["status"] == "pending"
    assert body["progress"] == 0


def test_import_status_404(client) -> None:
    assert client.get("/api/locations/999/import-status").status_code == 404


def test_create_rejects_invalid_lat(client) -> None:
    response = client.post(
        "/api/locations",
        json={"name": "Bad", "latitude": 200.0, "longitude": 0.0, "type": "own"},
    )
    assert response.status_code == 422


def test_update_partial(client) -> None:
    response = client.put("/api/locations/1", json={"note": "important"})
    assert response.status_code == 200
    assert response.json()["note"] == "important"
    assert response.json()["name"] == "Field A"  # unchanged


def test_update_404(client) -> None:
    assert client.put("/api/locations/999", json={"note": "x"}).status_code == 404


def test_delete(client) -> None:
    response = client.delete("/api/locations/1")
    assert response.status_code == 204
    assert client.get("/api/locations/1").status_code == 404


def test_delete_404(client) -> None:
    assert client.delete("/api/locations/999").status_code == 404
