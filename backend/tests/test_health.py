import pytest
from fastapi.testclient import TestClient

from app.api import health as health_module
from app.main import app


@pytest.fixture
def fake_db_ok(monkeypatch):
    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_module, "_check_database", _ok)


@pytest.fixture
def fake_db_down(monkeypatch):
    async def _down() -> bool:
        return False

    monkeypatch.setattr(health_module, "_check_database", _down)


def test_health_returns_ok_when_db_up(fake_db_ok) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"] == "0.1.0"
    assert "environment" in body


def test_health_reports_db_down(fake_db_down) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["database"] == "down"


def test_openapi_available() -> None:
    with TestClient(app) as client:
        response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Weather Agro API"
