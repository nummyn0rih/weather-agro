"""Tests for the history backfill service.

Uses an in-memory SQLite database (with TimescaleDB-specific bits avoided)
to verify that:

* `_yearly_chunks` slices a 10y window into year-sized pieces;
* `run_backfill` sets import_status `pending` → `in_progress` → `done` and
  reports progress 0–100;
* re-running backfill is idempotent (UPSERT, no duplicate rows).

The Postgres-only `INSERT … ON CONFLICT` syntax is replaced by SQLite's
equivalent `INSERT … ON CONFLICT … DO UPDATE` via SQLAlchemy's
``sqlalchemy.dialects.sqlite.insert``.
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
from app.db.models import Location, WeatherDaily
from app.services.weather import backfill, ingest
from app.services.weather.dto import WeatherDailyDTO


@pytest_asyncio.fixture
async def session_factory(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Bypass Postgres-specific extension/hypertable migrations and just create
    # the ORM-known tables. Drop FK to keep it simple in this in-memory DB.
    async with engine.begin() as conn:
        # Only create what backfill touches; full metadata pulls JSONB columns
        # that don't compile under SQLite.
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    Location.__table__,
                    WeatherDaily.__table__,
                ],
            )
        )

    factory = async_sessionmaker(engine, expire_on_commit=False)

    # Patch the upsert helpers to use SQLite dialect.
    async def sqlite_upsert(session, location_id, rows: Sequence[WeatherDailyDTO]) -> int:
        if not rows:
            return 0
        from dataclasses import asdict

        payload = [{**asdict(r), "location_id": location_id} for r in rows]
        stmt = sqlite_insert(WeatherDaily).values(payload)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in WeatherDaily.__table__.columns
            if c.name not in ("time", "location_id", "source")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["time", "location_id", "source"],
            set_=update_cols,
        )
        await session.execute(stmt)
        await session.commit()
        return len(payload)

    monkeypatch.setattr(ingest, "upsert_weather_daily", sqlite_upsert)

    yield factory

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_location(session_factory) -> int:
    async with session_factory() as session:
        loc = Location(
            name="Test",
            latitude=45.0,
            longitude=39.0,
            region="South",
            type="own",
            created_at=datetime.now(UTC),
            import_status="pending",
            import_progress=0,
        )
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        return loc.id


def test_yearly_chunks_splits_decade() -> None:
    chunks = backfill._yearly_chunks(date(2016, 4, 28), date(2026, 4, 28))
    # 10 full years + the final single day.
    assert len(chunks) == 11
    assert chunks[0] == (date(2016, 4, 28), date(2017, 4, 27))
    assert chunks[-1] == (date(2026, 4, 28), date(2026, 4, 28))
    # No gaps, no overlaps.
    for prev, nxt in zip(chunks, chunks[1:]):
        assert date.fromordinal(prev[1].toordinal() + 1) == nxt[0]


def test_yearly_chunks_short_range() -> None:
    chunks = backfill._yearly_chunks(date(2025, 1, 1), date(2025, 6, 1))
    assert chunks == [(date(2025, 1, 1), date(2025, 6, 1))]


async def test_run_backfill_sets_status_and_progress(
    session_factory, seeded_location
) -> None:
    location_id = seeded_location

    fetch_calls: list[tuple[date, date]] = []

    async def fake_om(lat, lon, dfrom, dto, *, location_id):
        fetch_calls.append((dfrom, dto))
        return [
            WeatherDailyDTO(
                time=dfrom,
                source="open_meteo",
                location_id=location_id,
                temp_avg=10.0,
            )
        ]

    async def fake_nasa(lat, lon, dfrom, dto, *, location_id):
        return [
            WeatherDailyDTO(
                time=dfrom,
                source="nasa_power",
                location_id=location_id,
                temp_avg=11.0,
            )
        ]

    await backfill.run_backfill(
        session_factory,
        location_id,
        years=2,
        today=date(2026, 4, 28),
        fetchers={"open_meteo": fake_om, "nasa_power": fake_nasa},
    )

    # 2-year window split into 3 chunks (2y + 1 trailing day) × 2 sources.
    assert len(fetch_calls) == 3

    async with session_factory() as session:
        loc = await session.get(Location, location_id)
        assert loc.import_status == "done"
        assert loc.import_progress == 100
        assert loc.import_started_at is not None
        assert loc.import_finished_at is not None

        rows = (
            (await session.execute(select(WeatherDaily))).scalars().all()
        )
        # 3 chunks × 2 sources = 6 rows, all distinct (time, source) pairs.
        assert len(rows) == 6
        sources = {r.source for r in rows}
        assert sources == {"open_meteo", "nasa_power"}


async def test_run_backfill_is_idempotent(session_factory, seeded_location) -> None:
    """Re-running the backfill must not duplicate rows (UPSERT)."""
    location_id = seeded_location

    async def fake_om(lat, lon, dfrom, dto, *, location_id):
        return [
            WeatherDailyDTO(
                time=dfrom,
                source="open_meteo",
                location_id=location_id,
                temp_avg=15.0,
            )
        ]

    fetchers = {"open_meteo": fake_om}

    await backfill.run_backfill(
        session_factory,
        location_id,
        years=1,
        today=date(2026, 4, 28),
        fetchers=fetchers,
    )
    async with session_factory() as session:
        first_count = len(
            (await session.execute(select(WeatherDaily))).scalars().all()
        )

    # Second run with overlapping date range — should overwrite, not duplicate.
    await backfill.run_backfill(
        session_factory,
        location_id,
        years=1,
        today=date(2026, 4, 28),
        fetchers=fetchers,
    )
    async with session_factory() as session:
        second_count = len(
            (await session.execute(select(WeatherDaily))).scalars().all()
        )

    assert first_count == second_count


async def test_run_backfill_marks_error_on_failure(
    session_factory, seeded_location
) -> None:
    location_id = seeded_location

    async def boom(lat, lon, dfrom, dto, *, location_id):
        raise RuntimeError("upstream exploded")

    # Wrap the whole orchestration so the unhandled error sets status=error.
    # The service swallows per-source fetch errors, so to trigger the
    # error branch we patch _set_status to raise mid-task.
    real_set_status = backfill._set_status
    calls = {"n": 0}

    async def flaky_set_status(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated db hiccup")
        return await real_set_status(*args, **kwargs)

    import app.services.weather.backfill as bf_mod

    bf_mod._set_status = flaky_set_status  # type: ignore[assignment]
    try:
        with pytest.raises(RuntimeError):
            await backfill.run_backfill(
                session_factory,
                location_id,
                years=1,
                today=date(2026, 4, 28),
                fetchers={"om": boom},
            )
    finally:
        bf_mod._set_status = real_set_status  # type: ignore[assignment]

    async with session_factory() as session:
        loc = await session.get(Location, location_id)
        assert loc.import_status == "error"
        assert loc.import_error and "simulated db hiccup" in loc.import_error
