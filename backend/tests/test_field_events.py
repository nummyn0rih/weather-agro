import io
from datetime import date, datetime, timezone
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api import events as events_api
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import FieldEvent, User
from app.db.session import get_db
from app.main import app
from app.services import field_event as event_service

_NOW = datetime(2026, 4, 30, tzinfo=timezone.utc)


def _make_event(
    id_: int = 1,
    location_id: int = 1,
    event_type: str = "note",
    event_date_: date | None = None,
    crop_id: int | None = None,
    description: str | None = "hello",
    photos: list[str] | None = None,
) -> FieldEvent:
    return FieldEvent(
        id=id_,
        location_id=location_id,
        event_type=event_type,
        event_date=event_date_ or date(2026, 4, 1),
        crop_id=crop_id,
        variety=None,
        area_hectares=None,
        yield_kg=None,
        quality_rating=None,
        description=description,
        photos=list(photos or []),
        created_at=_NOW,
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    # Sandbox uploads to a tmp dir so tests don't touch /uploads
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path), raising=False)

    store: dict[int, FieldEvent] = {1: _make_event()}

    async def fake_list(
        _session,
        location_id=None,
        event_type=None,
        crop_id=None,
        date_from=None,
        date_to=None,
    ):
        items = list(store.values())
        if location_id is not None:
            items = [e for e in items if e.location_id == location_id]
        if event_type is not None:
            items = [e for e in items if e.event_type == event_type]
        if crop_id is not None:
            items = [e for e in items if e.crop_id == crop_id]
        if date_from is not None:
            items = [e for e in items if e.event_date >= date_from]
        if date_to is not None:
            items = [e for e in items if e.event_date <= date_to]
        return items

    async def fake_get(_session, eid):
        return store.get(eid)

    async def fake_create(_session, data):
        new_id = max(store.keys(), default=0) + 1
        obj = FieldEvent(
            id=new_id,
            created_at=_NOW,
            photos=[],
            **data.model_dump(),
        )
        store[new_id] = obj
        return obj

    async def fake_update(_session, eid, data):
        if eid not in store:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(store[eid], k, v)
        return store[eid]

    async def fake_delete(_session, eid):
        return store.pop(eid, None)

    async def fake_add_photos(_session, event, urls):
        event.photos = list(event.photos) + urls
        return event

    async def fake_remove_photo(_session, event, url):
        event.photos = [p for p in event.photos if p != url]
        return event

    monkeypatch.setattr(event_service, "list_events", fake_list)
    monkeypatch.setattr(event_service, "get_event", fake_get)
    monkeypatch.setattr(event_service, "create_event", fake_create)
    monkeypatch.setattr(event_service, "update_event", fake_update)
    monkeypatch.setattr(event_service, "delete_event", fake_delete)
    monkeypatch.setattr(event_service, "add_photos", fake_add_photos)
    monkeypatch.setattr(event_service, "remove_photo", fake_remove_photo)

    async def fake_user() -> User:
        return User(id=1, username="admin", password_hash="x")

    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_list_returns_seed(client) -> None:
    response = client.get("/api/events")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == 1
    assert body[0]["event_type"] == "note"


def test_list_filter_by_location(client) -> None:
    assert len(client.get("/api/events?location_id=1").json()) == 1
    assert len(client.get("/api/events?location_id=2").json()) == 0


def test_list_filter_by_type_and_date(client) -> None:
    assert len(client.get("/api/events?event_type=note").json()) == 1
    assert len(client.get("/api/events?event_type=harvest").json()) == 0
    assert (
        len(client.get("/api/events?date_from=2026-05-01").json()) == 0
    )
    assert (
        len(client.get("/api/events?date_to=2026-04-30").json()) == 1
    )


def test_get_event(client) -> None:
    response = client.get("/api/events/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_event_404(client) -> None:
    assert client.get("/api/events/999").status_code == 404


def test_create_note_event(client) -> None:
    response = client.post(
        "/api/events",
        json={
            "location_id": 1,
            "event_type": "note",
            "event_date": "2026-04-15",
            "description": "checked the field",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 2
    assert body["event_type"] == "note"
    assert body["photos"] == []


def test_create_planting_requires_crop(client) -> None:
    response = client.post(
        "/api/events",
        json={
            "location_id": 1,
            "event_type": "planting",
            "event_date": "2026-04-15",
        },
    )
    assert response.status_code == 422


def test_create_harvest_requires_yield(client) -> None:
    response = client.post(
        "/api/events",
        json={
            "location_id": 1,
            "event_type": "harvest",
            "event_date": "2026-09-15",
            "crop_id": 1,
        },
    )
    assert response.status_code == 422


def test_update_partial(client) -> None:
    response = client.put(
        "/api/events/1", json={"description": "updated note"}
    )
    assert response.status_code == 200
    assert response.json()["description"] == "updated note"


def test_update_404(client) -> None:
    assert client.put("/api/events/999", json={}).status_code == 404


def test_delete(client) -> None:
    response = client.delete("/api/events/1")
    assert response.status_code == 204
    assert client.get("/api/events/1").status_code == 404


def test_delete_404(client) -> None:
    assert client.delete("/api/events/999").status_code == 404


def test_upload_photos_happy_path(client, tmp_path) -> None:
    img = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    files = [
        ("files", ("a.png", io.BytesIO(img), "image/png")),
        ("files", ("b.jpg", io.BytesIO(img), "image/jpeg")),
    ]
    response = client.post("/api/events/1/photos", files=files)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["photos"]) == 2
    for url in body["photos"]:
        assert url.startswith("/uploads/events/1/")


def test_upload_photo_extension_rejected(client) -> None:
    files = [
        ("files", ("evil.exe", io.BytesIO(b"MZ"), "application/octet-stream")),
    ]
    response = client.post("/api/events/1/photos", files=files)
    assert response.status_code == 400


def test_upload_photo_limit_enforced(client, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "MAX_PHOTOS_PER_EVENT", 1, raising=False)
    img = b"\x89PNG\r\n\x1a\n"
    files = [
        ("files", ("a.png", io.BytesIO(img), "image/png")),
        ("files", ("b.png", io.BytesIO(img), "image/png")),
    ]
    response = client.post("/api/events/1/photos", files=files)
    assert response.status_code == 400


def test_delete_photo(client) -> None:
    img = b"\x89PNG\r\n\x1a\n"
    upload = client.post(
        "/api/events/1/photos",
        files=[("files", ("a.png", io.BytesIO(img), "image/png"))],
    )
    assert upload.status_code == 200, upload.text
    url = upload.json()["photos"][0]
    filename = url.rsplit("/", 1)[-1]

    response = client.delete(f"/api/events/1/photos/{filename}")
    assert response.status_code == 200
    assert response.json()["photos"] == []


def test_delete_photo_not_found(client) -> None:
    response = client.delete("/api/events/1/photos/missing.png")
    assert response.status_code == 404
