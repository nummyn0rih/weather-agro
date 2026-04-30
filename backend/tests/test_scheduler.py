"""Tests for APScheduler jobs.

Uses an in-memory SQLite DB to verify:

* ``daily_ingest_job`` walks every location, calls each source, upserts rows,
  and writes a ``scheduler_logs`` row with status='success';
* ``forecast_refresh_job`` does the same for forecast (Open-Meteo only);
* a fetcher exception inside a job is contained — the run still records a
  ``success`` log (per-location errors are swallowed by design);
* a failure inside the orchestration is recorded with status='error'.

Postgres-only ``INSERT … ON CONFLICT`` is swapped for SQLite's equivalent
via monkey-patched upsert helpers, mirroring `test_backfill.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    Location,
    SchedulerLog,
    WeatherDaily,
    WeatherForecast,
)
from app.scheduler import jobs as jobs_mod
from app.services.weather import ingest
from app.services.weather.dto import WeatherDailyDTO


@pytest_asyncio.fixture
async def session_factory(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    Location.__table__,
                    WeatherDaily.__table__,
                    WeatherForecast.__table__,
                    SchedulerLog.__table__,
                ],
            )
        )

    factory = async_sessionmaker(engine, expire_on_commit=False)

    def _make_sqlite_upsert(table):
        async def _upsert(session, location_id, rows: Sequence[WeatherDailyDTO]) -> int:
            if not rows:
                return 0
            from dataclasses import asdict

            payload = [{**asdict(r), "location_id": location_id} for r in rows]
            stmt = sqlite_insert(table).values(payload)
            update_cols = {
                c.name: stmt.excluded[c.name]
                for c in table.__table__.columns
                if c.name not in ("time", "location_id", "source")
            }
            stmt = stmt.on_conflict_do_update(
                index_elements=["time", "location_id", "source"],
                set_=update_cols,
            )
            await session.execute(stmt)
            await session.commit()
            return len(payload)

        return _upsert

    monkeypatch.setattr(ingest, "upsert_weather_daily", _make_sqlite_upsert(WeatherDaily))
    monkeypatch.setattr(
        ingest, "upsert_weather_forecast", _make_sqlite_upsert(WeatherForecast)
    )

    yield factory

    await engine.dispose()


@pytest_asyncio.fixture
async def two_locations(session_factory) -> list[int]:
    async with session_factory() as session:
        ids: list[int] = []
        for name, lat, lon in (("A", 45.0, 39.0), ("B", 55.0, 37.0)):
            loc = Location(
                name=name,
                latitude=lat,
                longitude=lon,
                type="own",
                created_at=datetime.now(UTC),
                import_status="done",
                import_progress=100,
            )
            session.add(loc)
        await session.commit()
        result = await session.execute(select(Location.id).order_by(Location.id))
        ids = list(result.scalars().all())
    return ids


async def test_daily_ingest_job_writes_rows_and_log(
    session_factory, two_locations, monkeypatch
) -> None:
    target = date(2026, 4, 28)
    seen: list[tuple[int, str, date]] = []

    async def fake_om(lat, lon, dfrom, dto, *, location_id):
        seen.append((location_id, "open_meteo", dfrom))
        return [
            WeatherDailyDTO(
                time=dfrom, source="open_meteo", location_id=location_id, temp_avg=10.0
            )
        ]

    async def fake_nasa(lat, lon, dfrom, dto, *, location_id):
        seen.append((location_id, "nasa_power", dfrom))
        return [
            WeatherDailyDTO(
                time=dfrom, source="nasa_power", location_id=location_id, temp_avg=11.0
            )
        ]

    monkeypatch.setattr(jobs_mod.open_meteo, "fetch_historical", fake_om)
    monkeypatch.setattr(jobs_mod.nasa_power, "fetch_historical", fake_nasa)

    async def work(factory):
        return await jobs_mod._ingest_yesterday(factory, target_day=target)

    await jobs_mod._run_with_log(
        jobs_mod.DAILY_INGEST_JOB_ID, work, session_factory=session_factory
    )

    # 2 locations × 2 sources = 4 fetches, all for `target`.
    assert len(seen) == 4
    assert {s[2] for s in seen} == {target}
    assert {s[1] for s in seen} == {"open_meteo", "nasa_power"}

    async with session_factory() as session:
        rows = (await session.execute(select(WeatherDaily))).scalars().all()
        assert len(rows) == 4

        logs = (
            (
                await session.execute(
                    select(SchedulerLog).where(
                        SchedulerLog.job_id == jobs_mod.DAILY_INGEST_JOB_ID
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(logs) == 1
        log = logs[0]
        assert log.status == "success"
        assert log.items_processed == 4
        assert log.error is None
        assert log.duration_ms is not None and log.duration_ms >= 0


async def test_forecast_refresh_job_writes_rows_and_log(
    session_factory, two_locations, monkeypatch
) -> None:
    async def fake_forecast(lat, lon, days=16, *, location_id):
        return [
            WeatherDailyDTO(
                time=date(2026, 5, 1),
                source="open_meteo",
                location_id=location_id,
                temp_avg=18.0,
            )
        ]

    monkeypatch.setattr(jobs_mod.open_meteo, "fetch_forecast", fake_forecast)

    await jobs_mod.forecast_refresh_job(session_factory=session_factory)

    async with session_factory() as session:
        rows = (await session.execute(select(WeatherForecast))).scalars().all()
        assert len(rows) == 2

        log = (
            (
                await session.execute(
                    select(SchedulerLog).where(
                        SchedulerLog.job_id == jobs_mod.FORECAST_REFRESH_JOB_ID
                    )
                )
            )
            .scalars()
            .one()
        )
        assert log.status == "success"
        assert log.items_processed == 2


async def test_daily_ingest_swallows_per_location_failures(
    session_factory, two_locations, monkeypatch
) -> None:
    """One bad upstream call must not abort the whole run."""

    async def boom(lat, lon, dfrom, dto, *, location_id):
        raise RuntimeError("upstream 503")

    async def fake_nasa(lat, lon, dfrom, dto, *, location_id):
        return [
            WeatherDailyDTO(
                time=dfrom, source="nasa_power", location_id=location_id, temp_avg=9.0
            )
        ]

    monkeypatch.setattr(jobs_mod.open_meteo, "fetch_historical", boom)
    monkeypatch.setattr(jobs_mod.nasa_power, "fetch_historical", fake_nasa)

    await jobs_mod.daily_ingest_job(session_factory=session_factory)

    async with session_factory() as session:
        rows = (await session.execute(select(WeatherDaily))).scalars().all()
        # NASA succeeds for both locations; Open-Meteo failed for both.
        assert len(rows) == 2
        assert {r.source for r in rows} == {"nasa_power"}

        log = (
            (
                await session.execute(
                    select(SchedulerLog).where(
                        SchedulerLog.job_id == jobs_mod.DAILY_INGEST_JOB_ID
                    )
                )
            )
            .scalars()
            .one()
        )
        # Per-location errors are contained → run is still 'success'.
        assert log.status == "success"
        assert log.items_processed == 2


async def test_orchestration_failure_logged_as_error(
    session_factory, monkeypatch
) -> None:
    """If the work coroutine itself raises, the log row is status='error'."""

    async def broken_work(factory):
        raise RuntimeError("kaboom")

    await jobs_mod._run_with_log(
        "broken_job", broken_work, session_factory=session_factory
    )

    async with session_factory() as session:
        log = (
            (
                await session.execute(
                    select(SchedulerLog).where(SchedulerLog.job_id == "broken_job")
                )
            )
            .scalars()
            .one()
        )
        assert log.status == "error"
        assert log.error is not None and "kaboom" in log.error
        assert log.items_processed == 0


def test_create_scheduler_registers_default_jobs() -> None:
    from app.scheduler import create_scheduler

    sched = create_scheduler()
    ids = {j.id for j in sched.get_jobs()}
    assert ids == {
        jobs_mod.DAILY_INGEST_JOB_ID,
        jobs_mod.FORECAST_REFRESH_JOB_ID,
        jobs_mod.CLIMATE_NORMALS_JOB_ID,
        jobs_mod.EVALUATE_ALERTS_JOB_ID,
    }
    # Daily ingest must trigger at 03:00 Europe/Moscow.
    daily = sched.get_job(jobs_mod.DAILY_INGEST_JOB_ID)
    assert str(daily.trigger.timezone) == "Europe/Moscow"
    # Climate normals must trigger on day 1 of every month.
    normals = sched.get_job(jobs_mod.CLIMATE_NORMALS_JOB_ID)
    assert str(normals.trigger.timezone) == "Europe/Moscow"
