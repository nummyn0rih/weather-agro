"""Tests for the Telegram bot command handlers and bind-code lifecycle.

Uses an in-memory SQLite DB. JSONB-only tables (alert_rules) are skipped;
only the tables exercised by the handlers under test are created.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models import (
    AlertHistory,
    Location,
    User,
    WeatherDaily,
    WeatherForecast,
)
from app.services import telegram_bind
from app.telegram_bot import handlers


@pytest_asyncio.fixture
async def session_factory():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    User.__table__,
                    Location.__table__,
                    WeatherDaily.__table__,
                    WeatherForecast.__table__,
                    AlertHistory.__table__,
                ],
            )
        )
    factory = async_sessionmaker(eng, expire_on_commit=False)
    yield factory
    await eng.dispose()


@pytest_asyncio.fixture
async def user(session_factory) -> User:
    async with session_factory() as session:
        u = User(username="admin", password_hash="x")
        session.add(u)
        await session.commit()
        await session.refresh(u)
    return u


# ── Bind code lifecycle ─────────────────────────────────────────────


async def test_issue_bind_code_sets_fields(session_factory, user) -> None:
    async with session_factory() as session:
        u = await session.get(User, user.id)
        assert u is not None
        code, expires_at = await telegram_bind.issue_bind_code(
            session, u, ttl_seconds=300
        )
        assert code.isdigit() and len(code) == 8
        assert expires_at > datetime.now(UTC)


async def test_consume_bind_code_links_chat_id(session_factory, user) -> None:
    async with session_factory() as session:
        u = await session.get(User, user.id)
        assert u is not None
        code, _ = await telegram_bind.issue_bind_code(session, u, ttl_seconds=300)

    async with session_factory() as session:
        bound = await telegram_bind.consume_bind_code(session, code, chat_id=42)
        assert bound is not None
        assert bound.telegram_chat_id == 42
        assert bound.telegram_bind_code is None


async def test_consume_bind_code_rejects_expired(session_factory, user) -> None:
    past = datetime.now(UTC) - timedelta(seconds=10)
    async with session_factory() as session:
        u = await session.get(User, user.id)
        assert u is not None
        u.telegram_bind_code = "12345678"
        u.telegram_bind_code_expires_at = past
        await session.commit()

    async with session_factory() as session:
        result = await telegram_bind.consume_bind_code(
            session, "12345678", chat_id=7
        )
        assert result is None


async def test_consume_bind_code_unknown_returns_none(session_factory) -> None:
    async with session_factory() as session:
        result = await telegram_bind.consume_bind_code(session, "99999999", 7)
        assert result is None


# ── Pure helpers ────────────────────────────────────────────────────


def test_parse_period_days() -> None:
    assert handlers.parse_period("7d") == 7
    assert handlers.parse_period("2w") == 14
    assert handlers.parse_period("1m") == 30
    assert handlers.parse_period("1y") == 365


def test_parse_period_invalid() -> None:
    with pytest.raises(ValueError):
        handlers.parse_period("seven")
    with pytest.raises(ValueError):
        handlers.parse_period("0d")


# ── Auth gating ─────────────────────────────────────────────────────


async def test_unbound_chat_blocked_from_locations(session_factory) -> None:
    async with session_factory() as session:
        text = await handlers.handle_locations(session, chat_id=555, args=[])
    assert "не привязан" in text.lower()


async def test_unbound_chat_blocked_from_weather(session_factory) -> None:
    async with session_factory() as session:
        text = await handlers.handle_weather(session, 555, ["1"])
    assert "не привязан" in text.lower()


# ── /start binding flow ────────────────────────────────────────────


async def test_start_without_args_shows_instructions(
    session_factory,
) -> None:
    async with session_factory() as session:
        text = await handlers.handle_start(session, chat_id=1, args=[])
    assert "/start" in text


async def test_start_with_valid_code_binds(session_factory, user) -> None:
    async with session_factory() as session:
        u = await session.get(User, user.id)
        assert u is not None
        code, _ = await telegram_bind.issue_bind_code(session, u, ttl_seconds=300)

    async with session_factory() as session:
        text = await handlers.handle_start(session, chat_id=99, args=[code])
        assert "привязан" in text.lower()
        bound = await telegram_bind.get_user_by_chat_id(session, 99)
        assert bound is not None and bound.id == user.id


async def test_start_with_bad_code_rejected(session_factory) -> None:
    async with session_factory() as session:
        text = await handlers.handle_start(session, chat_id=99, args=["00000000"])
    assert "неверный" in text.lower() or "просроч" in text.lower()


# ── Bound commands return data ─────────────────────────────────────


@pytest_asyncio.fixture
async def bound_user(session_factory, user) -> tuple[User, int]:
    chat_id = 12345
    async with session_factory() as session:
        u = await session.get(User, user.id)
        assert u is not None
        u.telegram_chat_id = chat_id
        await session.commit()
    return user, chat_id


async def test_locations_lists_locations(session_factory, bound_user) -> None:
    _, chat_id = bound_user
    async with session_factory() as session:
        session.add(
            Location(name="Field A", latitude=45.0, longitude=39.0, type="own")
        )
        session.add(
            Location(name="Field B", latitude=46.0, longitude=40.0, type="reference")
        )
        await session.commit()

    async with session_factory() as session:
        text = await handlers.handle_locations(session, chat_id, [])
    assert "Field A" in text
    assert "Field B" in text


async def test_weather_returns_latest_day(session_factory, bound_user) -> None:
    _, chat_id = bound_user
    async with session_factory() as session:
        loc = Location(name="Krd", latitude=45.0, longitude=39.0, type="own")
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        session.add(
            WeatherDaily(
                time=date(2026, 4, 29),
                location_id=loc.id,
                source="open_meteo",
                temp_min=10.0,
                temp_max=22.0,
                temp_avg=16.0,
                precipitation=2.5,
                humidity_avg=65.0,
                wind_speed_avg=3.1,
            )
        )
        await session.commit()
        loc_id = loc.id

    async with session_factory() as session:
        text = await handlers.handle_weather(session, chat_id, [str(loc_id)])
    assert "Krd" in text
    assert "22.0" in text


async def test_weather_unknown_location(session_factory, bound_user) -> None:
    _, chat_id = bound_user
    async with session_factory() as session:
        text = await handlers.handle_weather(session, chat_id, ["9999"])
    assert "не найдена" in text.lower()


async def test_stats_summarises_period(session_factory, bound_user) -> None:
    _, chat_id = bound_user
    today = datetime(2026, 4, 30, tzinfo=UTC)
    async with session_factory() as session:
        loc = Location(name="Krd", latitude=45.0, longitude=39.0, type="own")
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        for i in range(3):
            session.add(
                WeatherDaily(
                    time=today.date() - timedelta(days=i),
                    location_id=loc.id,
                    source="open_meteo",
                    temp_min=5.0 + i,
                    temp_max=15.0 + i,
                    temp_avg=10.0 + i,
                    precipitation=1.0 + i,
                )
            )
        await session.commit()
        loc_id = loc.id

    async with session_factory() as session:
        text = await handlers.handle_stats(
            session, chat_id, [str(loc_id), "7d"], now=today
        )
    assert "Krd" in text
    assert "Темп" in text


async def test_forecast_uses_forecast_table(session_factory, bound_user) -> None:
    _, chat_id = bound_user
    today = datetime(2026, 4, 30, tzinfo=UTC)
    async with session_factory() as session:
        loc = Location(name="Krd", latitude=45.0, longitude=39.0, type="own")
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        for i in range(1, 4):
            session.add(
                WeatherForecast(
                    time=today.date() + timedelta(days=i),
                    location_id=loc.id,
                    source="open_meteo",
                    temp_min=10.0,
                    temp_max=20.0,
                    precipitation=0.5,
                )
            )
        await session.commit()
        loc_id = loc.id

    async with session_factory() as session:
        text = await handlers.handle_forecast(
            session, chat_id, [str(loc_id)], now=today
        )
    assert "Krd" in text
    assert "20.0" in text


async def test_alerts_history_empty(session_factory, bound_user) -> None:
    _, chat_id = bound_user
    async with session_factory() as session:
        text = await handlers.handle_alerts_history(session, chat_id, [])
    assert "Срабатываний" in text or "нет" in text.lower()
