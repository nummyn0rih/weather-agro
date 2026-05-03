from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


@pytest.fixture
def upload_file(tmp_path, monkeypatch):
    """Point UPLOAD_DIR at a tmp dir, drop a probe file, rebuild app mount."""
    settings = get_settings()
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

    # Re-mount /uploads against the temp dir so the existing app instance
    # serves from there for this test.
    from fastapi.staticfiles import StaticFiles

    # Drop any pre-existing /uploads mount.
    app.router.routes = [
        r for r in app.router.routes if getattr(r, "name", None) != "uploads"
    ]
    app.mount(
        "/uploads", StaticFiles(directory=str(tmp_path)), name="uploads"
    )

    events_dir = tmp_path / "events" / "1"
    events_dir.mkdir(parents=True)
    probe = events_dir / "probe.txt"
    probe.write_bytes(b"hello-photo")
    yield probe


def test_uploads_serves_existing_file(upload_file: Path) -> None:
    with TestClient(app) as c:
        rel = upload_file.relative_to(upload_file.parents[2])
        response = c.get(f"/uploads/{rel.as_posix()}")
    assert response.status_code == 200
    assert response.content == b"hello-photo"


def test_uploads_returns_404_for_missing(upload_file: Path) -> None:
    with TestClient(app) as c:
        response = c.get("/uploads/events/1/does-not-exist.jpg")
    assert response.status_code == 404
