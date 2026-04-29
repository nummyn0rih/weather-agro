"""Tests for anomalies service + `/api/analytics/anomalies` endpoint.

Pure classifier (`classify_anomaly`) and aggregator (`compute_anomalies`)
are exercised directly. Persistence + endpoint use an in-memory SQLite DB.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import analytics as analytics_api
from app.api.deps import get_current_user
from app.db.base import Base
from app.db.models import (
    ClimateNormal,
    Location,
    User,
    WeatherDaily,
)
from app.db.session import get_db
from app.main import app
from app.services.analytics.anomalies import (
    classify_anomaly,
    compute_anomalies,
    get_anomalies,
)


def test_classify_within_one_sigma_is_none() -> None:
    level, dev, sigma = classify_anomaly(11.0, 10.0, 2.0)
    assert level == "none"
    assert dev == pytest.approx(1.0)
    assert sigma == pytest.approx(0.5)


def test_classify_moderate_above_one_sigma() -> None:
    level, dev, sigma = classify_anomaly(13.0, 10.0, 2.0)
    assert level == "moderate"
    assert dev == pytest.approx(3.0)
    assert sigma == pytest.approx(1.5)


def test_classify_extreme_above_two_sigma() -> None:
    level, dev, sigma = classify_anomaly(15.0, 10.0, 2.0)
    assert level == "extreme"
    assert dev == pytest.approx(5.0)
    assert sigma == pytest.approx(2.5)


def test_classify_negative_deviation_uses_abs() -> None:
    level, dev, sigma = classify_anomaly(5.0, 10.0, 2.0)
    assert level == "extreme"
    assert dev == pytest.approx(-5.0)
    assert sigma == pytest.approx(-2.5)


def test_classify_no_value_or_no_mean_is_none() -> None:
    assert classify_anomaly(None, 10.0, 2.0) == ("none", None, None)
    assert classify_anomaly(10.0, None, 2.0) == ("none", None, None)


def test_classify_zero_or_missing_std_falls_back_to_none() -> None:
    level, dev, sigma = classify_anomaly(15.0, 10.0, 0.0)
    assert level == "none"
    assert dev == pytest.approx(5.0)
    assert sigma is None
    level2, _, sigma2 = classify_anomaly(15.0, 10.0, None)
    assert level2 == "none"
    assert sigma2 is None


def test_compute_anomalies_pairs_rows_with_bucket() -> None:
    rows = [
        {"time": date(2026, 4, 5), "location_id": 1, "temp_avg": 13.0},
        {"time": date(2026, 4, 6), "location_id": 1, "temp_avg": 16.0},
        {"time": date(2026, 5, 1), "location_id": 1, "temp_avg": 18.0},
    ]
    normals = [
        {"bucket": 4, "mean": 10.0, "std": 2.0},
        {"bucket": 5, "mean": 18.0, "std": 1.0},
    ]
    out = compute_anomalies(
        rows, normals=normals, parameter="temp_avg", period="month"
    )
    by_time = {r["time"]: r for r in out}
    assert by_time[date(2026, 4, 5)]["level"] == "moderate"
    assert by_time[date(2026, 4, 6)]["level"] == "extreme"
    assert by_time[date(2026, 4, 6)]["sigma"] == pytest.approx(3.0)
    assert by_time[date(2026, 5, 1)]["level"] == "none"


def test_compute_anomalies_missing_normal_yields_none_level() -> None:
    rows = [{"time": date(2026, 4, 1), "location_id": 1, "temp_avg": 100.0}]
    out = compute_anomalies(
        rows, normals=[], parameter="temp_avg", period="month"
    )
    assert out[0]["level"] == "none"
    assert out[0]["normal_mean"] is None
    assert out[0]["deviation"] is None


def test_compute_anomalies_orm_normals_supported() -> None:
    n = ClimateNormal(
        location_id=1,
        parameter="temp_avg",
        period="month",
        bucket=4,
        mean=10.0,
        std=2.0,
        min=8.0,
        max=12.0,
        count=4,
    )
    rows = [{"time": date(2026, 4, 1), "location_id": 1, "temp_avg": 15.0}]
    out = compute_anomalies(rows, normals=[n], parameter="temp_avg", period="month")
    assert out[0]["level"] == "extreme"
    assert out[0]["normal_mean"] == pytest.approx(10.0)


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    Location.__table__,
                    WeatherDaily.__table__,
                    ClimateNormal.__table__,
                ],
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

        for d, src, t in [
            (date(2026, 4, 1), "open_meteo", 9.0),
            (date(2026, 4, 1), "nasa_power", 11.0),  # avg → 10.0 (none)
            (date(2026, 4, 2), "open_meteo", 13.0),  # +1.5σ moderate
            (date(2026, 4, 3), "open_meteo", 16.0),  # +3σ extreme
        ]:
            session.add(
                WeatherDaily(
                    time=d,
                    location_id=loc_id,
                    source=src,
                    temp_avg=t,
                )
            )
        session.add(
            ClimateNormal(
                location_id=loc_id,
                parameter="temp_avg",
                period="month",
                bucket=4,
                mean=10.0,
                std=2.0,
                min=6.0,
                max=14.0,
                count=10,
                year_from=2015,
                year_to=2024,
            )
        )
        await session.commit()
    return loc_id


async def test_get_anomalies_uses_average_source(session_factory, seeded) -> None:
    async with session_factory() as session:
        out = await get_anomalies(
            session,
            location_id=seeded,
            parameter="temp_avg",
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 3),
            period="month",
            source="average",
        )
    by_time = {r["time"]: r for r in out}
    assert by_time[date(2026, 4, 1)]["value"] == pytest.approx(10.0)
    assert by_time[date(2026, 4, 1)]["level"] == "none"
    assert by_time[date(2026, 4, 2)]["level"] == "moderate"
    assert by_time[date(2026, 4, 3)]["level"] == "extreme"


async def test_get_anomalies_rejects_unknown_parameter(
    session_factory, seeded
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="Unknown parameter"):
            await get_anomalies(
                session,
                location_id=seeded,
                parameter="nope",
                date_from=date(2026, 4, 1),
                date_to=date(2026, 4, 3),
            )


async def test_get_anomalies_rejects_inverted_range(
    session_factory, seeded
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="date_from"):
            await get_anomalies(
                session,
                location_id=seeded,
                parameter="temp_avg",
                date_from=date(2026, 4, 5),
                date_to=date(2026, 4, 1),
            )


@pytest.fixture
def client(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_get(_session, **kwargs):
        captured.update(kwargs)
        return [
            {
                "time": date(2026, 4, 2),
                "location_id": kwargs["location_id"],
                "parameter": kwargs["parameter"],
                "value": 13.0,
                "normal_mean": 10.0,
                "normal_std": 2.0,
                "deviation": 3.0,
                "sigma": 1.5,
                "level": "moderate",
                "bucket": 4,
                "period": kwargs["period"],
            }
        ]

    monkeypatch.setattr(
        analytics_api.anomalies_service, "get_anomalies", fake_get
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


def test_endpoint_returns_anomaly_rows(client) -> None:
    c, captured = client
    response = c.get(
        "/api/analytics/anomalies",
        params={
            "location_id": 1,
            "parameter": "temp_avg",
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["level"] == "moderate"
    assert row["sigma"] == pytest.approx(1.5)
    assert captured["location_id"] == 1
    assert captured["parameter"] == "temp_avg"
    assert captured["period"] == "month"
    assert captured["source"] == "average"
    assert captured["date_from"] == date(2026, 4, 1)
    assert captured["date_to"] == date(2026, 4, 30)


def test_endpoint_validates_period(client) -> None:
    c, _ = client
    response = c.get(
        "/api/analytics/anomalies",
        params={
            "location_id": 1,
            "parameter": "temp_avg",
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
            "period": "decade",
        },
    )
    assert response.status_code == 422


def test_endpoint_unknown_parameter_returns_400(monkeypatch, client) -> None:
    c, _ = client

    async def boom(*_args, **_kwargs):
        raise ValueError("Unknown parameter: nope")

    monkeypatch.setattr(
        analytics_api.anomalies_service, "get_anomalies", boom
    )
    response = c.get(
        "/api/analytics/anomalies",
        params={
            "location_id": 1,
            "parameter": "nope",
            "date_from": "2026-04-01",
            "date_to": "2026-04-30",
        },
    )
    assert response.status_code == 400
    assert "Unknown parameter" in response.json()["detail"]
