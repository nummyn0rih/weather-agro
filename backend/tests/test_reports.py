"""Happy-path tests for /api/reports endpoints.

Heavyweight deps (WeasyPrint, matplotlib) are mocked: we exercise the wiring
between the API, background task runner, and DB without rendering a real PDF.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import Location, Report, User
from app.db.session import get_db
from app.main import app
from app.services.reports import service as report_service

_NOW = datetime(2026, 4, 30, tzinfo=timezone.utc)


def _make_loc(id_: int = 1) -> Location:
    return Location(
        id=id_,
        name="Field A",
        latitude=45.0,
        longitude=39.0,
        region="South",
        type="own",
        note=None,
        created_at=_NOW,
        import_status="done",
        import_progress=100,
    )


@pytest.fixture
def client(monkeypatch, tmp_path):
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path), raising=False)

    locations: dict[int, Location] = {1: _make_loc()}
    reports: dict[int, Report] = {}
    next_id = {"v": 0}

    class FakeSession:
        async def get(self, model, key):
            if model is Location:
                return locations.get(key)
            if model is Report:
                return reports.get(key)
            return None

    fake_session = FakeSession()

    async def fake_db() -> AsyncIterator[FakeSession]:
        yield fake_session

    async def fake_create(_session, *, location_id, season_year):
        next_id["v"] += 1
        rid = next_id["v"]
        obj = Report(
            id=rid,
            location_id=location_id,
            season_year=season_year,
            status="pending",
            file_path=None,
            file_size_bytes=None,
            error=None,
            created_at=_NOW,
            finished_at=None,
        )
        reports[rid] = obj
        return obj

    async def fake_get(_session, report_id):
        return reports.get(report_id)

    async def fake_run_generation(_factory, *, report_id, upload_dir):
        obj = reports[report_id]
        path = Path(upload_dir) / "reports" / f"{report_id}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4 fake\n")
        obj.status = "done"
        obj.file_path = str(path)
        obj.file_size_bytes = path.stat().st_size
        obj.finished_at = _NOW

    monkeypatch.setattr(report_service, "create_pending_report", fake_create)
    monkeypatch.setattr(report_service, "get_report", fake_get)
    monkeypatch.setattr(report_service, "run_generation", fake_run_generation)

    async def fake_user() -> User:
        return User(id=1, username="admin", password_hash="x")

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_generate_returns_pending_id(client) -> None:
    response = client.post(
        "/api/reports/generate",
        json={"location_id": 1, "season_year": 2026},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["id"] == 1
    assert body["location_id"] == 1
    assert body["season_year"] == 2026
    # After background task runs in TestClient, status flips to "done"
    meta = client.get(f"/api/reports/{body['id']}").json()
    assert meta["status"] == "done"
    assert meta["file_size_bytes"] is not None and meta["file_size_bytes"] > 0


def test_generate_unknown_location(client) -> None:
    response = client.post(
        "/api/reports/generate",
        json={"location_id": 999, "season_year": 2026},
    )
    assert response.status_code == 404


def test_download_happy_path(client) -> None:
    create = client.post(
        "/api/reports/generate",
        json={"location_id": 1, "season_year": 2025},
    )
    assert create.status_code == 202
    file_id = create.json()["id"]

    response = client.get(f"/api/reports/{file_id}/download")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_download_missing(client) -> None:
    assert client.get("/api/reports/9999/download").status_code == 404


def test_endpoints_require_auth() -> None:
    """No Authorization header → 401 on every reports endpoint."""
    with TestClient(app) as c:
        r1 = c.post("/api/reports/generate", json={"location_id": 1, "season_year": 2026})
        r2 = c.get("/api/reports")
        r3 = c.get("/api/reports/1")
        r4 = c.get("/api/reports/1/download")
    for r in (r1, r2, r3, r4):
        assert r.status_code == 401, r.text


def test_download_pending_returns_409(client, monkeypatch) -> None:
    # Disable the auto-complete background task to keep the report "pending".
    async def noop(_factory, *, report_id, upload_dir):
        return None

    monkeypatch.setattr(report_service, "run_generation", noop)

    create = client.post(
        "/api/reports/generate",
        json={"location_id": 1, "season_year": 2024},
    )
    file_id = create.json()["id"]
    response = client.get(f"/api/reports/{file_id}/download")
    assert response.status_code == 409
