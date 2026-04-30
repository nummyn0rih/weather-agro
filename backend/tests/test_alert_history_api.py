"""Tests for GET /api/alerts/history (task 4.4.1).

The route is exercised via TestClient with the query service mocked, in the
same style as ``test_alert_rules.py`` / ``test_locations.py``. Filter and
pagination wiring is verified against the captured kwargs that the route
forwarded to the service. Snapshot mapping (``rule_name``, ``parameter``, ...
from ``*_snapshot`` columns) and the ``location_name='(удалена)'`` fallback
are checked by inspecting the JSON shape the route returns.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.models import AlertHistory, Location, User
from app.db.session import get_db
from app.main import app
from app.services.alerts import history as history_service

_TRIGGERED = datetime(2026, 4, 29, 12, 0, tzinfo=UTC)


def _loc(id_: int = 1, name: str = "Field A") -> Location:
    return Location(
        id=id_,
        name=name,
        latitude=45.0,
        longitude=39.0,
        type="own",
        import_status="done",
        import_progress=100,
    )


def _hist(
    id_: int,
    *,
    rule_id: int | None = 1,
    location_id: int | None = 1,
    location: Location | None = None,
    rule_name_snapshot: str = "Heat",
    parameter_snapshot: str = "temperature_max",
    condition_snapshot: str = "gt",
    threshold_snapshot: float = 30.0,
    threshold_max_snapshot: float | None = None,
    value: float = 35.0,
    triggered_at: datetime = _TRIGGERED,
    message: str = "Heat: temperature_max=35.00 > 30.00 (location_id=1)",
) -> AlertHistory:
    h = AlertHistory(
        id=id_,
        rule_id=rule_id,
        location_id=location_id,
        triggered_at=triggered_at,
        value=value,
        message=message,
        rule_name_snapshot=rule_name_snapshot,
        parameter_snapshot=parameter_snapshot,
        condition_snapshot=condition_snapshot,
        threshold_snapshot=threshold_snapshot,
        threshold_max_snapshot=threshold_max_snapshot,
    )
    # Pre-populate the relationship so the route does not lazy-load (lazy='raise').
    h.location = location
    return h


@pytest.fixture
def client(monkeypatch):
    captured: dict[str, Any] = {}

    loc1 = _loc(1, "Field A")
    loc2 = _loc(2, "Field B")

    rows: list[AlertHistory] = [
        _hist(10, rule_id=1, location_id=1, location=loc1),
        _hist(11, rule_id=1, location_id=2, location=loc2, value=33.0),
        _hist(12, rule_id=2, location_id=1, location=loc1, rule_name_snapshot="Frost"),
        # rule deleted — rule_id NULL, snapshot retained
        _hist(13, rule_id=None, location_id=1, location=loc1, rule_name_snapshot="Old rule"),
        # location deleted — location_id NULL, no relationship object
        _hist(14, rule_id=1, location_id=None, location=None),
    ]

    async def fake_query(
        _session,
        *,
        location_id=None,
        rule_id=None,
        date_from=None,
        date_to=None,
        limit=50,
        offset=0,
    ):
        captured["location_id"] = location_id
        captured["rule_id"] = rule_id
        captured["date_from"] = date_from
        captured["date_to"] = date_to
        captured["limit"] = limit
        captured["offset"] = offset

        filtered = rows
        if location_id is not None:
            filtered = [r for r in filtered if r.location_id == location_id]
        if rule_id is not None:
            filtered = [r for r in filtered if r.rule_id == rule_id]
        # Sort triggered_at DESC then id DESC for deterministic ordering.
        ordered = sorted(filtered, key=lambda r: (r.triggered_at, r.id), reverse=True)
        total = len(ordered)
        page = ordered[offset : offset + limit]
        return page, total

    monkeypatch.setattr(history_service, "query_history", fake_query)

    async def fake_user() -> User:
        return User(id=1, username="admin", password_hash="x")

    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        c.captured = captured  # type: ignore[attr-defined]
        yield c

    app.dependency_overrides.clear()


def test_list_default_returns_all_with_total(client) -> None:
    response = client.get("/api/alerts/history")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert len(body["items"]) == 5
    item = body["items"][0]
    # Snapshot fields surface as flat names.
    assert {
        "id",
        "rule_id",
        "rule_name",
        "location_id",
        "location_name",
        "parameter",
        "condition",
        "threshold",
        "threshold_max",
        "value",
        "triggered_at",
        "message",
    } <= item.keys()


def test_filter_by_location_id(client) -> None:
    response = client.get("/api/alerts/history?location_id=2")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert all(it["location_id"] == 2 for it in body["items"])
    assert client.captured["location_id"] == 2


def test_filter_by_rule_id(client) -> None:
    response = client.get("/api/alerts/history?rule_id=2")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["rule_name"] == "Frost"
    assert client.captured["rule_id"] == 2


def test_filter_by_date_range_forwarded(client) -> None:
    response = client.get(
        "/api/alerts/history?date_from=2026-04-01&date_to=2026-04-30"
    )
    assert response.status_code == 200
    assert client.captured["date_from"].isoformat() == "2026-04-01"
    assert client.captured["date_to"].isoformat() == "2026-04-30"


def test_pagination_limit_offset(client) -> None:
    page1 = client.get("/api/alerts/history?limit=2&offset=0").json()
    page2 = client.get("/api/alerts/history?limit=2&offset=2").json()
    assert page1["total"] == 5
    assert page2["total"] == 5
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    ids1 = {it["id"] for it in page1["items"]}
    ids2 = {it["id"] for it in page2["items"]}
    assert ids1.isdisjoint(ids2)


def test_pagination_limit_validation(client) -> None:
    assert client.get("/api/alerts/history?limit=0").status_code == 422
    assert client.get("/api/alerts/history?limit=201").status_code == 422
    assert client.get("/api/alerts/history?offset=-1").status_code == 422


def test_empty_result(client) -> None:
    response = client.get("/api/alerts/history?location_id=999")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_orphan_rule_uses_snapshot_name(client) -> None:
    response = client.get("/api/alerts/history")
    assert response.status_code == 200
    items = response.json()["items"]
    orphan = next(it for it in items if it["id"] == 13)
    assert orphan["rule_id"] is None
    assert orphan["rule_name"] == "Old rule"


def test_deleted_location_label(client) -> None:
    response = client.get("/api/alerts/history")
    assert response.status_code == 200
    items = response.json()["items"]
    orphan = next(it for it in items if it["id"] == 14)
    assert orphan["location_id"] is None
    assert orphan["location_name"] == "(удалена)"


def test_unauthenticated_returns_401(monkeypatch) -> None:
    # No dependency override — real auth applies and rejects missing token.
    with TestClient(app) as c:
        response = c.get("/api/alerts/history")
        assert response.status_code == 401


async def test_date_to_is_inclusive_end_of_day() -> None:
    """date_to=YYYY-MM-DD must match rows with triggered_at on that date,
    even at 23:59 UTC. Hits the real query builder against in-memory SQLite."""
    from datetime import date, datetime

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.base import Base
    from app.db.models import AlertHistory, Location
    from app.services.alerts import history as history_service

    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda sc: Base.metadata.create_all(
                sc, tables=[Location.__table__, AlertHistory.__table__]
            )
        )
    factory = async_sessionmaker(eng, expire_on_commit=False)

    async with factory() as session:
        session.add(
            Location(
                id=1,
                name="A",
                latitude=45.0,
                longitude=39.0,
                type="own",
                import_status="done",
                import_progress=100,
            )
        )
        await session.commit()
        for ts in (
            datetime(2026, 4, 30, 0, 0, 0, tzinfo=UTC),
            datetime(2026, 4, 30, 23, 59, 59, tzinfo=UTC),
            datetime(2026, 5, 1, 0, 0, 0, tzinfo=UTC),
        ):
            session.add(
                AlertHistory(
                    rule_id=None,
                    location_id=1,
                    triggered_at=ts,
                    value=1.0,
                    message="x",
                    rule_name_snapshot="R",
                    parameter_snapshot="temperature_max",
                    condition_snapshot="gt",
                    threshold_snapshot=0.0,
                )
            )
        await session.commit()

        rows, total = await history_service.query_history(
            session,
            date_from=date(2026, 4, 30),
            date_to=date(2026, 4, 30),
        )
        triggered = sorted(r.triggered_at for r in rows)
        assert total == 2
        assert triggered[0].day == 30 and triggered[0].hour == 0
        assert triggered[1].day == 30 and triggered[1].hour == 23
    await eng.dispose()
