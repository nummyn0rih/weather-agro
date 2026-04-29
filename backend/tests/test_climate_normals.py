"""Tests for climate normals service + `/api/analytics/normals` endpoint.

Pure aggregator (`compute_normals_from_rows`) is exercised directly with
hand-crafted rows. Persistence + endpoint use an in-memory SQLite DB.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
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
from app.services.analytics.climate_normals import (
    NORMAL_PARAMETERS,
    NORMAL_PERIODS,
    _bucket_for,
    calculate_normals,
    compute_normals_from_rows,
    get_cached_normals,
    recompute_all,
    recompute_normals_for_location,
    upsert_normals,
)


def test_bucket_for_periods() -> None:
    d = date(2026, 4, 29)
    assert _bucket_for(d, "month") == 4
    assert _bucket_for(d, "week") == d.isocalendar().week
    assert _bucket_for(d, "doy") == d.timetuple().tm_yday


def test_bucket_for_unknown_period_raises() -> None:
    with pytest.raises(ValueError):
        _bucket_for(date(2026, 4, 1), "decade")  # type: ignore[arg-type]


def test_compute_normals_month_mean_std_min_max() -> None:
    rows = [
        {"time": date(2024, 4, 1), "location_id": 1, "temp_avg": 8.0},
        {"time": date(2024, 4, 15), "location_id": 1, "temp_avg": 12.0},
        {"time": date(2025, 4, 5), "location_id": 1, "temp_avg": 10.0},
        {"time": date(2025, 4, 20), "location_id": 1, "temp_avg": 14.0},
        {"time": date(2026, 5, 1), "location_id": 1, "temp_avg": 18.0},
    ]
    out = compute_normals_from_rows(
        rows, location_id=1, parameter="temp_avg", period="month"
    )
    by_bucket = {r["bucket"]: r for r in out}

    apr = by_bucket[4]
    assert apr["mean"] == pytest.approx(11.0)
    assert apr["min"] == pytest.approx(8.0)
    assert apr["max"] == pytest.approx(14.0)
    assert apr["count"] == 4
    assert apr["year_from"] == 2024
    assert apr["year_to"] == 2025
    # Sample std of [8, 12, 10, 14] ≈ 2.582
    assert apr["std"] == pytest.approx(2.5819, rel=1e-3)

    may = by_bucket[5]
    assert may["count"] == 1
    assert may["std"] == 0.0


def test_compute_normals_skips_none_but_records_year() -> None:
    rows = [
        {"time": date(2024, 4, 1), "location_id": 1, "temp_avg": None},
        {"time": date(2025, 4, 1), "location_id": 1, "temp_avg": 10.0},
    ]
    out = compute_normals_from_rows(
        rows, location_id=1, parameter="temp_avg", period="month"
    )
    apr = next(r for r in out if r["bucket"] == 4)
    assert apr["count"] == 1
    assert apr["mean"] == pytest.approx(10.0)
    # year_from picks up both years because the bucket was touched.
    assert apr["year_from"] == 2024
    assert apr["year_to"] == 2025


def test_compute_normals_all_none_yields_zero_count_row() -> None:
    rows = [
        {"time": date(2024, 4, 1), "location_id": 1, "temp_avg": None},
    ]
    out = compute_normals_from_rows(
        rows, location_id=1, parameter="temp_avg", period="month"
    )
    assert len(out) == 1
    assert out[0]["count"] == 0
    assert out[0]["mean"] is None
    assert out[0]["std"] is None


def test_compute_normals_doy_buckets() -> None:
    rows = [
        {"time": date(2024, 1, 1), "location_id": 1, "temp_avg": -5.0},
        {"time": date(2025, 1, 1), "location_id": 1, "temp_avg": -3.0},
    ]
    out = compute_normals_from_rows(
        rows, location_id=1, parameter="temp_avg", period="doy"
    )
    assert len(out) == 1
    assert out[0]["bucket"] == 1
    assert out[0]["mean"] == pytest.approx(-4.0)


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
async def location_with_data(session_factory) -> int:
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

        # Two years of April data, two sources to exercise the average path.
        rows = [
            (date(2024, 4, 1), "open_meteo", 10.0),
            (date(2024, 4, 1), "nasa_power", 12.0),  # avg → 11.0
            (date(2024, 4, 15), "open_meteo", 14.0),
            (date(2025, 4, 1), "open_meteo", 8.0),
            (date(2025, 4, 20), "open_meteo", 16.0),
        ]
        for d, src, t in rows:
            session.add(
                WeatherDaily(
                    time=d,
                    location_id=loc_id,
                    source=src,
                    temp_avg=t,
                )
            )
        await session.commit()
    return loc_id


async def test_calculate_normals_uses_cross_source_average(
    session_factory, location_with_data
) -> None:
    async with session_factory() as session:
        out = await calculate_normals(
            session,
            location_id=location_with_data,
            parameter="temp_avg",
            period="month",
        )
    apr = next(r for r in out if r["bucket"] == 4)
    # Daily averages: 11.0 (2024-04-01 from 10+12), 14.0, 8.0, 16.0
    assert apr["count"] == 4
    assert apr["mean"] == pytest.approx((11.0 + 14.0 + 8.0 + 16.0) / 4)
    assert apr["year_from"] == 2024
    assert apr["year_to"] == 2025


async def test_calculate_normals_rejects_unknown_parameter(
    session_factory, location_with_data
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="Unknown parameter"):
            await calculate_normals(
                session,
                location_id=location_with_data,
                parameter="nope",
                period="month",
            )


async def test_calculate_normals_rejects_unknown_period(
    session_factory, location_with_data
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="Unknown period"):
            await calculate_normals(
                session,
                location_id=location_with_data,
                parameter="temp_avg",
                period="decade",  # type: ignore[arg-type]
            )


async def test_upsert_normals_replaces_existing(
    session_factory, location_with_data
) -> None:
    async with session_factory() as session:
        await upsert_normals(
            session,
            location_id=location_with_data,
            parameter="temp_avg",
            period="month",
            rows=[
                {
                    "location_id": location_with_data,
                    "parameter": "temp_avg",
                    "period": "month",
                    "bucket": 4,
                    "mean": 10.0,
                    "std": 1.0,
                    "min": 9.0,
                    "max": 11.0,
                    "count": 2,
                    "year_from": 2024,
                    "year_to": 2025,
                }
            ],
        )

    async with session_factory() as session:
        cached = await get_cached_normals(
            session,
            location_id=location_with_data,
            parameter="temp_avg",
            period="month",
        )
        assert len(cached) == 1
        assert cached[0].mean == pytest.approx(10.0)

    # Replace with two buckets and confirm the old single row is gone.
    async with session_factory() as session:
        await upsert_normals(
            session,
            location_id=location_with_data,
            parameter="temp_avg",
            period="month",
            rows=[
                {
                    "location_id": location_with_data,
                    "parameter": "temp_avg",
                    "period": "month",
                    "bucket": 4,
                    "mean": 12.0,
                    "std": 2.0,
                    "min": 10.0,
                    "max": 14.0,
                    "count": 4,
                    "year_from": 2024,
                    "year_to": 2025,
                },
                {
                    "location_id": location_with_data,
                    "parameter": "temp_avg",
                    "period": "month",
                    "bucket": 5,
                    "mean": 18.0,
                    "std": 0.0,
                    "min": 18.0,
                    "max": 18.0,
                    "count": 1,
                    "year_from": 2026,
                    "year_to": 2026,
                },
            ],
        )

    async with session_factory() as session:
        cached = await get_cached_normals(
            session,
            location_id=location_with_data,
            parameter="temp_avg",
            period="month",
        )
        by_bucket = {r.bucket: r for r in cached}
        assert set(by_bucket) == {4, 5}
        assert by_bucket[4].mean == pytest.approx(12.0)
        assert by_bucket[4].count == 4


async def test_recompute_normals_persists_for_one_location(
    session_factory, location_with_data
) -> None:
    async with session_factory() as session:
        written = await recompute_normals_for_location(
            session,
            location_id=location_with_data,
            parameters=["temp_avg"],
            periods=["month"],
        )
    assert written >= 1

    async with session_factory() as session:
        result = await session.execute(
            select(ClimateNormal).where(
                ClimateNormal.location_id == location_with_data,
                ClimateNormal.parameter == "temp_avg",
                ClimateNormal.period == "month",
            )
        )
        rows = list(result.scalars().all())
        assert len(rows) == 1
        assert rows[0].bucket == 4
        assert rows[0].count == 4


async def test_recompute_all_walks_every_location(session_factory) -> None:
    async with session_factory() as session:
        for name in ("A", "B"):
            session.add(
                Location(
                    name=name,
                    latitude=45.0,
                    longitude=39.0,
                    type="own",
                    created_at=datetime.now(UTC),
                    import_status="done",
                    import_progress=100,
                )
            )
        await session.commit()
        result = await session.execute(select(Location.id).order_by(Location.id))
        ids = list(result.scalars().all())
        for lid in ids:
            session.add(
                WeatherDaily(
                    time=date(2024, 4, 1),
                    location_id=lid,
                    source="open_meteo",
                    temp_avg=10.0,
                )
            )
        await session.commit()

    async with session_factory() as session:
        total = await recompute_all(session)
    # Only `temp_avg` has values; collapse_to_average drops all-None days for
    # other params, yielding 0 rows. So total = 1 bucket × 3 periods × 2 locs.
    assert total == 2 * len(NORMAL_PERIODS)

    async with session_factory() as session:
        result = await session.execute(
            select(ClimateNormal).where(ClimateNormal.parameter == "temp_avg")
        )
        rows = list(result.scalars().all())
    assert len(rows) == 2 * len(NORMAL_PERIODS)


@pytest.fixture
def client(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_cached(_session, **kwargs):
        captured.update(kwargs)
        return [
            ClimateNormal(
                id=1,
                location_id=kwargs["location_id"],
                parameter=kwargs["parameter"],
                period=kwargs["period"],
                bucket=4,
                mean=11.0,
                std=2.5,
                min=8.0,
                max=14.0,
                count=4,
                year_from=2024,
                year_to=2025,
                updated_at=datetime(2026, 4, 1, tzinfo=UTC),
            )
        ]

    monkeypatch.setattr(
        analytics_api.normals_service, "get_cached_normals", fake_cached
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


def test_endpoint_returns_cached_rows(client) -> None:
    c, captured = client
    response = c.get(
        "/api/analytics/normals",
        params={
            "location_id": 1,
            "parameter": "temp_avg",
            "period": "month",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    row = body[0]
    assert row["bucket"] == 4
    assert row["mean"] == pytest.approx(11.0)
    assert row["count"] == 4
    assert captured["location_id"] == 1
    assert captured["parameter"] == "temp_avg"
    assert captured["period"] == "month"


def test_endpoint_validates_period(client) -> None:
    c, _ = client
    response = c.get(
        "/api/analytics/normals",
        params={
            "location_id": 1,
            "parameter": "temp_avg",
            "period": "decade",
        },
    )
    assert response.status_code == 422


def test_endpoint_refresh_recomputes(monkeypatch, client) -> None:
    c, _ = client

    calls: dict[str, object] = {}

    async def fake_calculate(_session, **kwargs):
        calls["calculate"] = kwargs
        return [
            {
                "location_id": kwargs["location_id"],
                "parameter": kwargs["parameter"],
                "period": kwargs["period"],
                "bucket": 4,
                "mean": 12.0,
                "std": 1.5,
                "min": 10.0,
                "max": 14.0,
                "count": 5,
                "year_from": 2020,
                "year_to": 2025,
            }
        ]

    async def fake_upsert(_session, **kwargs):
        calls["upsert"] = {**kwargs, "row_count": len(kwargs["rows"])}
        return len(kwargs["rows"])

    monkeypatch.setattr(
        analytics_api.normals_service, "calculate_normals", fake_calculate
    )
    monkeypatch.setattr(
        analytics_api.normals_service, "upsert_normals", fake_upsert
    )

    response = c.get(
        "/api/analytics/normals",
        params={
            "location_id": 7,
            "parameter": "precipitation",
            "period": "month",
            "refresh": "true",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body[0]["mean"] == pytest.approx(12.0)
    assert calls["calculate"] == {
        "location_id": 7,
        "parameter": "precipitation",
        "period": "month",
    }
    assert calls["upsert"]["row_count"] == 1


def test_endpoint_unknown_parameter_returns_400(monkeypatch, client) -> None:
    c, _ = client

    async def boom(*_args, **_kwargs):
        raise ValueError("Unknown parameter: nope")

    monkeypatch.setattr(
        analytics_api.normals_service, "calculate_normals", boom
    )
    response = c.get(
        "/api/analytics/normals",
        params={
            "location_id": 1,
            "parameter": "nope",
            "period": "month",
            "refresh": "true",
        },
    )
    assert response.status_code == 400
    assert "Unknown parameter" in response.json()["detail"]


def test_normal_periods_constants_align() -> None:
    assert set(NORMAL_PERIODS) == {"month", "week", "doy"}
    assert "temp_avg" in NORMAL_PARAMETERS
