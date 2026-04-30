"""Tests for the alert evaluation engine.

Uses an in-memory SQLite DB and constructs ``AlertRule`` objects in
Python (the alert_rules table uses PostgreSQL JSONB, which doesn't
compile under SQLite). The engine accepts already-loaded rule objects
via ``evaluate_rule``, so this is sufficient for unit coverage of:

* condition primitives (gt / lt / eq / between);
* multi-source averaging on weather_daily;
* fan-out to all locations when ``location_ids`` is empty;
* dedup window suppressing repeat alerts;
* disabled rules being skipped.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import AlertHistory, AlertRule, Location, WeatherDaily
from app.services.alerts import engine as alerts_engine


@pytest_asyncio.fixture
async def session_factory():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    Location.__table__,
                    WeatherDaily.__table__,
                    AlertHistory.__table__,
                ],
            )
        )
    factory = async_sessionmaker(eng, expire_on_commit=False)
    yield factory
    await eng.dispose()


@pytest_asyncio.fixture
async def two_locations(session_factory) -> list[int]:
    async with session_factory() as session:
        for name, lat, lon in (("A", 45.0, 39.0), ("B", 55.0, 37.0)):
            session.add(
                Location(
                    name=name,
                    latitude=lat,
                    longitude=lon,
                    type="own",
                    created_at=datetime.now(UTC),
                    import_status="done",
                    import_progress=100,
                )
            )
        await session.commit()
        ids = list(
            (await session.execute(select(Location.id).order_by(Location.id)))
            .scalars()
            .all()
        )
    return ids


def _rule(
    id_: int = 1,
    name: str = "Heat",
    parameter: str = "temperature_max",
    condition: str = "gt",
    threshold: float = 30.0,
    threshold_max: float | None = None,
    location_ids: list[int] | None = None,
    enabled: bool = True,
) -> AlertRule:
    return AlertRule(
        id=id_,
        name=name,
        parameter=parameter,
        condition=condition,
        threshold=threshold,
        threshold_max=threshold_max,
        location_ids=location_ids or [],
        enabled=enabled,
        telegram=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


# ── Pure-function condition checks ────────────────────────────────────


def test_check_condition_gt() -> None:
    assert alerts_engine.check_condition(31.0, "gt", 30.0)
    assert not alerts_engine.check_condition(30.0, "gt", 30.0)


def test_check_condition_lt() -> None:
    assert alerts_engine.check_condition(-6.0, "lt", -5.0)
    assert not alerts_engine.check_condition(-5.0, "lt", -5.0)


def test_check_condition_eq() -> None:
    assert alerts_engine.check_condition(20.0001, "eq", 20.0)
    assert not alerts_engine.check_condition(20.5, "eq", 20.0)


def test_check_condition_between() -> None:
    assert alerts_engine.check_condition(22.0, "between", 18.0, 26.0)
    assert not alerts_engine.check_condition(30.0, "between", 18.0, 26.0)
    assert not alerts_engine.check_condition(22.0, "between", 18.0, None)


# ── Engine-level evaluation ───────────────────────────────────────────


async def _seed_weather(
    session_factory,
    location_id: int,
    target_day: date,
    *,
    temp_max_per_source: dict[str, float],
) -> None:
    async with session_factory() as session:
        for source, tmax in temp_max_per_source.items():
            session.add(
                WeatherDaily(
                    time=target_day,
                    location_id=location_id,
                    source=source,
                    temp_max=tmax,
                )
            )
        await session.commit()


async def test_rule_triggers_when_threshold_exceeded(
    session_factory, two_locations
) -> None:
    target = date(2026, 4, 28)
    await _seed_weather(
        session_factory,
        two_locations[0],
        target,
        temp_max_per_source={"open_meteo": 35.0, "nasa_power": 33.0},
    )
    await _seed_weather(
        session_factory,
        two_locations[1],
        target,
        temp_max_per_source={"open_meteo": 25.0, "nasa_power": 24.0},
    )
    rule = _rule(threshold=30.0)
    now = datetime(2026, 4, 29, 6, 0, tzinfo=UTC)

    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session, rule, target_day=target, now=now
        )
        assert len(created) == 1
        assert created[0].location_id == two_locations[0]
        # Mean of 35.0 and 33.0 is 34.0.
        assert created[0].value == pytest.approx(34.0)
        assert "temperature_max" in created[0].message

        rows = (await session.execute(select(AlertHistory))).scalars().all()
        assert len(rows) == 1


async def test_dedup_blocks_repeat_within_window(
    session_factory, two_locations
) -> None:
    target = date(2026, 4, 28)
    await _seed_weather(
        session_factory,
        two_locations[0],
        target,
        temp_max_per_source={"open_meteo": 36.0},
    )
    rule = _rule(threshold=30.0)
    first_run = datetime(2026, 4, 29, 6, 0, tzinfo=UTC)
    second_run = first_run + timedelta(hours=2)

    async with session_factory() as session:
        first = await alerts_engine.evaluate_rule(
            session, rule, target_day=target, now=first_run, dedup_hours=6
        )
        assert len(first) == 1

        second = await alerts_engine.evaluate_rule(
            session, rule, target_day=target, now=second_run, dedup_hours=6
        )
        assert second == []

        rows = (await session.execute(select(AlertHistory))).scalars().all()
        assert len(rows) == 1


async def test_dedup_allows_repeat_after_window(
    session_factory, two_locations
) -> None:
    target = date(2026, 4, 28)
    await _seed_weather(
        session_factory,
        two_locations[0],
        target,
        temp_max_per_source={"open_meteo": 36.0},
    )
    rule = _rule(threshold=30.0)
    first_run = datetime(2026, 4, 29, 6, 0, tzinfo=UTC)
    later_run = first_run + timedelta(hours=8)

    async with session_factory() as session:
        await alerts_engine.evaluate_rule(
            session, rule, target_day=target, now=first_run, dedup_hours=6
        )
        again = await alerts_engine.evaluate_rule(
            session, rule, target_day=target, now=later_run, dedup_hours=6
        )
        assert len(again) == 1


async def test_empty_location_ids_fans_out_to_all(
    session_factory, two_locations
) -> None:
    target = date(2026, 4, 28)
    for loc in two_locations:
        await _seed_weather(
            session_factory,
            loc,
            target,
            temp_max_per_source={"open_meteo": 36.0},
        )
    rule = _rule(threshold=30.0, location_ids=[])
    now = datetime(2026, 4, 29, 6, 0, tzinfo=UTC)

    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session, rule, target_day=target, now=now
        )
        assert {c.location_id for c in created} == set(two_locations)


async def test_disabled_rule_skipped(session_factory, two_locations) -> None:
    target = date(2026, 4, 28)
    await _seed_weather(
        session_factory,
        two_locations[0],
        target,
        temp_max_per_source={"open_meteo": 40.0},
    )
    rule = _rule(threshold=30.0, enabled=False)

    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session,
            rule,
            target_day=target,
            now=datetime(2026, 4, 29, 6, 0, tzinfo=UTC),
        )
        assert created == []


async def test_no_weather_data_no_trigger(session_factory, two_locations) -> None:
    rule = _rule(threshold=30.0, location_ids=[two_locations[0]])
    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session,
            rule,
            target_day=date(2026, 4, 28),
            now=datetime(2026, 4, 29, 6, 0, tzinfo=UTC),
        )
        assert created == []


async def test_between_rule_triggers_inside_range(
    session_factory, two_locations
) -> None:
    target = date(2026, 4, 28)
    async with session_factory() as session:
        session.add(
            WeatherDaily(
                time=target,
                location_id=two_locations[0],
                source="open_meteo",
                temp_avg=22.0,
            )
        )
        await session.commit()
    rule = _rule(
        parameter="temperature_avg",
        condition="between",
        threshold=18.0,
        threshold_max=26.0,
        location_ids=[two_locations[0]],
    )

    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session,
            rule,
            target_day=target,
            now=datetime(2026, 4, 29, 6, 0, tzinfo=UTC),
        )
        assert len(created) == 1
        assert created[0].value == pytest.approx(22.0)


async def test_unsupported_parameter_does_not_crash(
    session_factory, two_locations
) -> None:
    rule = _rule(parameter="pressure_avg", threshold=1000.0)
    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session,
            rule,
            target_day=date(2026, 4, 28),
            now=datetime(2026, 4, 29, 6, 0, tzinfo=UTC),
        )
        assert created == []
