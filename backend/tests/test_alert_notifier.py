"""Tests for the Telegram alert notifier.

Covers message formatting, retry behaviour of ``send_telegram_message``,
fan-out across all bound users in ``notify_alert``, opt-out via the
rule's ``telegram`` flag, and the engine wiring that calls the notifier
once per created ``AlertHistory`` row.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from tenacity import wait_none

from app.db.base import Base
from app.db.models import AlertHistory, AlertRule, Location, User, WeatherDaily
from app.services.alerts import engine as alerts_engine
from app.services.alerts import notifier as notifier_module
from app.services.alerts.notifier import (
    format_alert_message,
    notify_alert,
    send_telegram_message,
)


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
                    User.__table__,
                ],
            )
        )
    factory = async_sessionmaker(eng, expire_on_commit=False)
    yield factory
    await eng.dispose()


def _rule(
    id_: int = 1,
    name: str = "Heat",
    parameter: str = "temperature_max",
    telegram: bool = True,
) -> AlertRule:
    return AlertRule(
        id=id_,
        name=name,
        parameter=parameter,
        condition="gt",
        threshold=30.0,
        threshold_max=None,
        location_ids=[],
        enabled=True,
        telegram=telegram,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _history(
    value: float = 35.5,
    location_id: int | None = 1,
    *,
    rule: AlertRule | None = None,
    **overrides: object,
) -> AlertHistory:
    snapshot_defaults = {
        "rule_name_snapshot": rule.name if rule else "Heat",
        "parameter_snapshot": rule.parameter if rule else "temperature_max",
        "condition_snapshot": rule.condition if rule else "gt",
        "threshold_snapshot": rule.threshold if rule else 30.0,
        "threshold_max_snapshot": rule.threshold_max if rule else None,
    }
    base = {
        "id": 10,
        "rule_id": rule.id if rule else 1,
        "location_id": location_id,
        "triggered_at": datetime(2026, 4, 29, 6, 30, tzinfo=UTC),
        "value": value,
        "message": "ignored — notifier formats its own",
        **snapshot_defaults,
    }
    base.update(overrides)
    return AlertHistory(**base)


# ── Formatting ───────────────────────────────────────────────────────


def test_format_alert_message_includes_all_fields() -> None:
    rule = _rule(name="Heatwave", parameter="temperature_max")
    history = _history(value=34.7)
    out = format_alert_message(rule, history, "Field A")

    assert "🔥" in out
    assert "Heatwave" in out
    assert "Field A" in out
    assert "temperature_max" in out
    assert "34.70" in out
    assert "°C" in out
    assert "2026-04-29 06:30" in out


def test_format_alert_message_falls_back_to_generic_emoji() -> None:
    rule = _rule(parameter="unknown_param")
    history = _history()
    out = format_alert_message(rule, history, "Field A")
    assert "🚨" in out


# ── send_telegram_message retry ──────────────────────────────────────


def _patch_no_wait(monkeypatch) -> None:
    """AsyncRetrying is built fresh per call; patch wait_exponential factory."""
    monkeypatch.setattr(notifier_module, "wait_exponential", lambda **_: wait_none())


async def test_send_succeeds_on_first_try(monkeypatch) -> None:
    _patch_no_wait(monkeypatch)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await send_telegram_message(client, "tok", 123, "hi")
    assert calls["n"] == 1


async def test_send_retries_on_transport_error(monkeypatch) -> None:
    _patch_no_wait(monkeypatch)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        await send_telegram_message(client, "tok", 123, "hi")
    assert calls["n"] == 3


async def test_send_gives_up_after_three_attempts(monkeypatch) -> None:
    _patch_no_wait(monkeypatch)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="upstream down")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await send_telegram_message(client, "tok", 123, "hi")
    assert calls["n"] == 3


# ── notify_alert fan-out ─────────────────────────────────────────────


async def _seed_location(session_factory, name: str = "Field A") -> int:
    async with session_factory() as session:
        loc = Location(
            name=name,
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
        return loc.id


async def _seed_users(session_factory, chat_ids: list[int | None]) -> None:
    async with session_factory() as session:
        for i, cid in enumerate(chat_ids):
            session.add(
                User(
                    username=f"u{i}",
                    password_hash="x",
                    telegram_chat_id=cid,
                )
            )
        await session.commit()


async def test_notify_alert_sends_to_every_bound_chat(
    monkeypatch, session_factory
) -> None:
    _patch_no_wait(monkeypatch)
    loc_id = await _seed_location(session_factory)
    await _seed_users(session_factory, [111, 222, None])

    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        import json

        seen.append(json.loads(body)["chat_id"])
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        async with session_factory() as session:
            sent = await notify_alert(
                session,
                client,
                "tok",
                _rule(),
                _history(location_id=loc_id),
            )

    assert sent == 2
    assert sorted(seen) == [111, 222]


async def test_notify_alert_skipped_when_telegram_disabled(
    session_factory,
) -> None:
    loc_id = await _seed_location(session_factory)
    await _seed_users(session_factory, [111])

    transport = httpx.MockTransport(
        lambda r: pytest.fail("should not call Telegram")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        async with session_factory() as session:
            sent = await notify_alert(
                session,
                client,
                "tok",
                _rule(telegram=False),
                _history(location_id=loc_id),
            )
    assert sent == 0


async def test_notify_alert_no_bound_users_returns_zero(
    session_factory,
) -> None:
    loc_id = await _seed_location(session_factory)
    await _seed_users(session_factory, [None, None])

    transport = httpx.MockTransport(
        lambda r: pytest.fail("should not call Telegram")
    )
    async with httpx.AsyncClient(transport=transport) as client:
        async with session_factory() as session:
            sent = await notify_alert(
                session,
                client,
                "tok",
                _rule(),
                _history(location_id=loc_id),
            )
    assert sent == 0


async def test_notify_alert_one_chat_failure_does_not_block_others(
    monkeypatch, session_factory
) -> None:
    _patch_no_wait(monkeypatch)
    loc_id = await _seed_location(session_factory)
    await _seed_users(session_factory, [111, 222])

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        chat_id = json.loads(request.read())["chat_id"]
        if chat_id == 111:
            return httpx.Response(500, text="bad")
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        async with session_factory() as session:
            sent = await notify_alert(
                session,
                client,
                "tok",
                _rule(),
                _history(location_id=loc_id),
            )
    assert sent == 1


# ── engine wiring ────────────────────────────────────────────────────


async def test_engine_invokes_notifier_per_created_history(
    session_factory,
) -> None:
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

        session.add(
            WeatherDaily(
                time=date(2026, 4, 28),
                location_id=loc_id,
                source="open_meteo",
                temp_max=36.0,
            )
        )
        await session.commit()

    rule = _rule()
    rule.location_ids = [loc_id]
    calls: list[tuple[int, int]] = []

    async def fake_notifier(r: AlertRule, h: AlertHistory) -> None:
        calls.append((r.id, h.location_id))

    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session,
            rule,
            target_day=date(2026, 4, 28),
            now=datetime(2026, 4, 29, 6, 0, tzinfo=UTC),
            notifier=fake_notifier,
        )

    assert len(created) == 1
    assert calls == [(rule.id, loc_id)]


async def test_engine_swallows_notifier_failure(session_factory) -> None:
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

        session.add(
            WeatherDaily(
                time=date(2026, 4, 28),
                location_id=loc_id,
                source="open_meteo",
                temp_max=36.0,
            )
        )
        await session.commit()

    rule = _rule()
    rule.location_ids = [loc_id]

    async def boom(r: AlertRule, h: AlertHistory) -> None:
        raise RuntimeError("nope")

    async with session_factory() as session:
        created = await alerts_engine.evaluate_rule(
            session,
            rule,
            target_day=date(2026, 4, 28),
            now=datetime(2026, 4, 29, 6, 0, tzinfo=UTC),
            notifier=boom,
        )

    assert len(created) == 1
