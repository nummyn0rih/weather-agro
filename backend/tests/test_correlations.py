"""Tests for correlations service + `/api/analytics/correlations` endpoint.

The pure aggregator (`compute_correlations`) is exercised directly. The
DB-backed `get_correlations` and the FastAPI endpoint use an in-memory
SQLite DB and a stub user dependency.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import analytics as analytics_api
from app.api.deps import get_current_user
from app.db.base import Base
from app.db.models import Location, User, WeatherDaily
from app.db.session import get_db
from app.main import app
from app.services.analytics.correlations import (
    compute_correlations,
    get_correlations,
)


def test_compute_returns_identity_diagonal() -> None:
    rows = [
        {"temp_avg": 1.0, "precipitation": 5.0},
        {"temp_avg": 2.0, "precipitation": 4.0},
        {"temp_avg": 3.0, "precipitation": 3.0},
    ]
    out = compute_correlations(rows, ["temp_avg", "precipitation"])
    assert out["parameters"] == ["temp_avg", "precipitation"]
    assert out["matrix"][0][0] == pytest.approx(1.0)
    assert out["matrix"][1][1] == pytest.approx(1.0)


def test_compute_perfect_negative_correlation() -> None:
    rows = [
        {"x": 1.0, "y": 5.0},
        {"x": 2.0, "y": 4.0},
        {"x": 3.0, "y": 3.0},
        {"x": 4.0, "y": 2.0},
    ]
    out = compute_correlations(rows, ["x", "y"])
    assert out["matrix"][0][1] == pytest.approx(-1.0)
    assert out["matrix"][1][0] == pytest.approx(-1.0)


def test_compute_zero_variance_yields_none() -> None:
    rows = [
        {"x": 5.0, "y": 1.0},
        {"x": 5.0, "y": 2.0},
        {"x": 5.0, "y": 3.0},
    ]
    out = compute_correlations(rows, ["x", "y"])
    # Constant series → no correlation defined
    assert out["matrix"][0][1] is None
    assert out["matrix"][1][0] is None
    # Constant vs itself → still None (zero variance)
    assert out["matrix"][0][0] is None
    # Non-constant diagonal stays 1
    assert out["matrix"][1][1] == pytest.approx(1.0)


def test_compute_pairwise_nan_deletion() -> None:
    rows = [
        {"x": 1.0, "y": 1.0, "z": None},
        {"x": 2.0, "y": 2.0, "z": 4.0},
        {"x": 3.0, "y": None, "z": 6.0},
        {"x": 4.0, "y": 4.0, "z": 8.0},
    ]
    out = compute_correlations(rows, ["x", "y", "z"])
    # x↔y: rows 0,1,3 → 3 paired observations
    assert out["counts"][0][1] == 3
    # x↔z: rows 1,2,3 → 3
    assert out["counts"][0][2] == 3
    # y↔z: rows 1,3 → 2
    assert out["counts"][1][2] == 2
    # Perfect linear pairs
    assert out["matrix"][0][1] == pytest.approx(1.0)
    assert out["matrix"][0][2] == pytest.approx(1.0)
    assert out["matrix"][1][2] == pytest.approx(1.0)
    assert out["n"] == 4


def test_compute_insufficient_samples_yields_none() -> None:
    rows = [{"x": 1.0, "y": 1.0}]
    out = compute_correlations(rows, ["x", "y"])
    assert out["matrix"][0][1] is None
    assert out["counts"][0][1] == 1


def test_compute_empty_inputs() -> None:
    assert compute_correlations([], ["x", "y"])["matrix"] == [
        [None, None],
        [None, None],
    ]
    assert compute_correlations([{"x": 1.0}], [])["parameters"] == []


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[Location.__table__, WeatherDaily.__table__],
            )
        )

    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(session_factory) -> int:
    async with session_factory() as session:
        loc = Location(
            name="A",
            latitude=45.0,
            longitude=39.0,
            type="own",
            created_at=datetime.now(UTC),
            import_status="done",
            import_progress=100,
        )
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        loc_id = loc.id

        # 4 days, two sources, perfect linear temp_avg vs et0 after averaging
        rows = [
            (date(2026, 4, 1), "open_meteo", 9.0, 1.0),
            (date(2026, 4, 1), "nasa_power", 11.0, 3.0),  # avg → 10, 2
            (date(2026, 4, 2), "open_meteo", 12.0, 4.0),
            (date(2026, 4, 3), "open_meteo", 14.0, 6.0),
            (date(2026, 4, 4), "open_meteo", 16.0, 8.0),
        ]
        for d, src, t, e in rows:
            session.add(
                WeatherDaily(
                    time=d,
                    location_id=loc_id,
                    source=src,
                    temp_avg=t,
                    et0=e,
                )
            )
        await session.commit()
    return loc_id


async def test_get_correlations_average_source(session_factory, seeded) -> None:
    async with session_factory() as session:
        out = await get_correlations(
            session,
            location_id=seeded,
            parameters=["temp_avg", "et0"],
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 4),
            source="average",
        )
    assert out["parameters"] == ["temp_avg", "et0"]
    assert out["n"] == 4
    coef = out["matrix"][0][1]
    assert coef is not None
    assert math.isclose(coef, 1.0, abs_tol=1e-9)
    assert out["counts"][0][1] == 4


async def test_get_correlations_rejects_unknown_parameter(
    session_factory, seeded
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="Unknown parameters"):
            await get_correlations(
                session,
                location_id=seeded,
                parameters=["temp_avg", "nope"],
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 4),
            )


async def test_get_correlations_rejects_inverted_range(
    session_factory, seeded
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="date_from"):
            await get_correlations(
                session,
                location_id=seeded,
                parameters=["temp_avg", "et0"],
                date_from=date(2026, 4, 5),
                date_to=date(2026, 4, 1),
            )


async def test_get_correlations_rejects_empty_parameters(
    session_factory, seeded
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="At least one parameter"):
            await get_correlations(
                session,
                location_id=seeded,
                parameters=[],
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 4),
            )


@pytest.fixture
def client(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_get(_session, **kwargs):
        captured.update(kwargs)
        params = list(kwargs["parameters"])
        n = len(params)
        return {
            "parameters": params,
            "matrix": [[1.0 if i == j else 0.5 for j in range(n)] for i in range(n)],
            "counts": [[10 for _ in range(n)] for _ in range(n)],
            "n": 10,
        }

    monkeypatch.setattr(
        analytics_api.correlations_service, "get_correlations", fake_get
    )

    async def fake_user() -> User:
        return User(id=1, username="admin", password_hash="x")

    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        yield c, captured

    app.dependency_overrides.clear()


def test_endpoint_returns_matrix(client) -> None:
    c, captured = client
    response = c.get(
        "/api/analytics/correlations",
        params=[
            ("location_id", 1),
            ("parameters", "temp_avg"),
            ("parameters", "precipitation"),
            ("date_from", "2026-04-01"),
            ("date_to", "2026-04-30"),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert body["parameters"] == ["temp_avg", "precipitation"]
    assert body["matrix"][0][0] == pytest.approx(1.0)
    assert body["matrix"][0][1] == pytest.approx(0.5)
    assert body["n"] == 10
    assert captured["location_id"] == 1
    assert list(captured["parameters"]) == ["temp_avg", "precipitation"]
    assert captured["source"] == "average"
    assert captured["date_from"] == date(2026, 4, 1)
    assert captured["date_to"] == date(2026, 4, 30)


def test_endpoint_validates_source(client) -> None:
    c, _ = client
    response = c.get(
        "/api/analytics/correlations",
        params=[
            ("location_id", 1),
            ("parameters", "temp_avg"),
            ("parameters", "et0"),
            ("date_from", "2026-04-01"),
            ("date_to", "2026-04-30"),
            ("source", "invalid_src"),
        ],
    )
    assert response.status_code == 422


def test_endpoint_unknown_parameter_returns_400(monkeypatch, client) -> None:
    c, _ = client

    async def boom(*_args, **_kwargs):
        raise ValueError("Unknown parameters: ['nope']")

    monkeypatch.setattr(
        analytics_api.correlations_service, "get_correlations", boom
    )
    response = c.get(
        "/api/analytics/correlations",
        params=[
            ("location_id", 1),
            ("parameters", "nope"),
            ("parameters", "temp_avg"),
            ("date_from", "2026-04-01"),
            ("date_to", "2026-04-30"),
        ],
    )
    assert response.status_code == 400
    assert "Unknown parameters" in response.json()["detail"]
