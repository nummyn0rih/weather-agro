"""DoD tests for task 4.4.0: AlertHistory snapshot fields + ON DELETE SET NULL.

Uses an isolated SQLite fixture with PRAGMA foreign_keys=ON so FK semantics
(SET NULL) are actually enforced. The shared fixture in test_alert_engine.py
keeps PRAGMA off and a partial schema; documented in BACKLOG.md.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest_asyncio
from sqlalchemy import event, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.base import Base
from app.db.models import AlertHistory, AlertRule, Location, WeatherDaily
from app.services.alerts import engine as alerts_engine


@compiles(JSONB, "sqlite")
def _jsonb_to_sqlite_json(_element, _compiler, **_kw):
    """Render JSONB columns as plain JSON on SQLite — production stays Postgres."""
    return "JSON"


@pytest_asyncio.fixture
async def session_factory_fk():
    """SQLite fixture with PRAGMA foreign_keys=ON.

    Cherry-picked FK-closed subset:
        Location               (no outgoing FK)
        WeatherDaily           → Location
        AlertRule              (no outgoing FK)
        AlertHistory           → AlertRule, Location

    Adding any model to this list requires re-checking that all FK targets
    are present, otherwise create_all will fail or runtime FK checks misbehave.
    Full Base.metadata.create_all is not portable to SQLite due to
    Postgres-specific server_defaults (e.g. alert_rules.location_ids '[]'::jsonb).
    See BACKLOG.md "Test fixture FK gap".
    """
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(eng.sync_engine, "connect")
    def _enable_fk(dbapi_conn, _connection_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    # alert_rules.location_ids declares Postgres-specific server_default
    # ("'[]'::jsonb") — SQLite chokes on the cast literal during create_all.
    # Strip and restore around DDL so production metadata is unchanged.
    loc_ids_col = AlertRule.__table__.c.location_ids
    saved_default = loc_ids_col.server_default
    loc_ids_col.server_default = None
    try:
        async with eng.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn,
                    tables=[
                        Location.__table__,
                        WeatherDaily.__table__,
                        AlertRule.__table__,
                        AlertHistory.__table__,
                    ],
                )
            )
            result = await conn.execute(text("PRAGMA foreign_keys"))
            fk_state = result.scalar()
            assert fk_state == 1, f"PRAGMA foreign_keys not enabled: got {fk_state!r}"
    finally:
        loc_ids_col.server_default = saved_default

    factory = async_sessionmaker(eng, expire_on_commit=False)
    yield factory
    await eng.dispose()


async def _seed_rule_and_location(session_factory) -> tuple[int, int]:
    async with session_factory() as session:
        loc = Location(
            name="Field A",
            latitude=45.0,
            longitude=39.0,
            type="own",
            import_status="done",
            import_progress=100,
        )
        session.add(loc)
        await session.commit()
        await session.refresh(loc)

        rule = AlertRule(
            name="Heat",
            parameter="temperature_max",
            condition="gt",
            threshold=30.0,
            threshold_max=None,
            location_ids=[loc.id],
            enabled=True,
            telegram=True,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)

        return rule.id, loc.id


async def _seed_weather(session_factory, location_id: int, target_day: date) -> None:
    async with session_factory() as session:
        session.add(
            WeatherDaily(
                time=target_day,
                location_id=location_id,
                source="open_meteo",
                temp_max=42.0,
                fetched_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def _fire_once(session_factory, rule_id: int, target_day: date) -> None:
    async with session_factory() as session:
        rule = await session.get(AlertRule, rule_id)
        await alerts_engine.evaluate_rule(
            session,
            rule,
            target_day=target_day,
            now=datetime(2026, 4, 29, 12, 0, tzinfo=UTC),
        )


# ── T1: snapshot populated on engine fire ────────────────────────────


async def test_engine_populates_snapshot_fields_on_fire(session_factory_fk):
    rule_id, loc_id = await _seed_rule_and_location(session_factory_fk)
    target_day = date(2026, 4, 29)
    await _seed_weather(session_factory_fk, loc_id, target_day)
    await _fire_once(session_factory_fk, rule_id, target_day)

    async with session_factory_fk() as session:
        h = (await session.execute(select(AlertHistory))).scalar_one()
        assert h.rule_id == rule_id
        assert h.location_id == loc_id
        assert h.rule_name_snapshot == "Heat"
        assert h.parameter_snapshot == "temperature_max"
        assert h.condition_snapshot == "gt"
        assert h.threshold_snapshot == 30.0
        assert h.threshold_max_snapshot is None


# ── T2: model accepts NULL rule_id on direct insert ──────────────────


async def test_model_accepts_null_rule_id(session_factory_fk):
    _, loc_id = await _seed_rule_and_location(session_factory_fk)
    async with session_factory_fk() as session:
        h = AlertHistory(
            rule_id=None,
            location_id=loc_id,
            triggered_at=datetime(2026, 4, 29, 12, 0, tzinfo=UTC),
            value=42.0,
            message="orphan",
            rule_name_snapshot="(deleted rule)",
            parameter_snapshot="temperature_max",
            condition_snapshot="gt",
            threshold_snapshot=30.0,
            threshold_max_snapshot=None,
        )
        session.add(h)
        await session.commit()
        await session.refresh(h)
        assert h.rule_id is None
        assert h.location_id == loc_id
        assert h.rule_name_snapshot == "(deleted rule)"


# ── T3: ON DELETE SET NULL on alert_rules.id ─────────────────────────


async def test_delete_rule_sets_rule_id_null_keeps_snapshot(session_factory_fk):
    rule_id, loc_id = await _seed_rule_and_location(session_factory_fk)
    target_day = date(2026, 4, 29)
    await _seed_weather(session_factory_fk, loc_id, target_day)
    await _fire_once(session_factory_fk, rule_id, target_day)

    async with session_factory_fk() as session:
        rule = await session.get(AlertRule, rule_id)
        await session.delete(rule)
        await session.commit()

    async with session_factory_fk() as session:
        h = (await session.execute(select(AlertHistory))).scalar_one()
        assert h.rule_id is None
        assert h.rule_name_snapshot == "Heat"
        assert h.parameter_snapshot == "temperature_max"
        assert h.condition_snapshot == "gt"
        assert h.threshold_snapshot == 30.0


# ── T4: ON DELETE SET NULL on locations.id ───────────────────────────


async def test_delete_location_sets_location_id_null(session_factory_fk):
    rule_id, loc_id = await _seed_rule_and_location(session_factory_fk)
    target_day = date(2026, 4, 29)
    await _seed_weather(session_factory_fk, loc_id, target_day)
    await _fire_once(session_factory_fk, rule_id, target_day)

    async with session_factory_fk() as session:
        loc = await session.get(Location, loc_id)
        await session.delete(loc)
        await session.commit()

    async with session_factory_fk() as session:
        h = (await session.execute(select(AlertHistory))).scalar_one()
        assert h.location_id is None
        assert h.rule_id == rule_id
        assert h.rule_name_snapshot == "Heat"


# ── T5: snapshot frozen after rule mutation ──────────────────────────


async def test_snapshot_unchanged_when_rule_mutated_post_fire(session_factory_fk):
    rule_id, loc_id = await _seed_rule_and_location(session_factory_fk)
    target_day = date(2026, 4, 29)
    await _seed_weather(session_factory_fk, loc_id, target_day)
    await _fire_once(session_factory_fk, rule_id, target_day)

    async with session_factory_fk() as session:
        rule = await session.get(AlertRule, rule_id)
        rule.name = "RENAMED"
        rule.parameter = "humidity_avg"
        rule.threshold = 99.0
        await session.commit()

    async with session_factory_fk() as session:
        h = (await session.execute(select(AlertHistory))).scalar_one()
        assert h.rule_name_snapshot == "Heat"
        assert h.parameter_snapshot == "temperature_max"
        assert h.threshold_snapshot == 30.0
