"""Tests for the universal `/api/weather/daily` query endpoint.

The aggregation primitives are pure functions, so we exercise them directly
with hand-crafted rows. The endpoint itself is covered by a small TestClient
test that monkeypatches the service layer.
"""

from __future__ import annotations

from datetime import date
from typing import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from app.api import weather as weather_api
from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services.weather.query import (
    _bucket_start,
    aggregate_buckets,
    collapse_to_average,
)


def test_bucket_start_week_aligns_to_monday() -> None:
    # 2026-04-29 is a Wednesday → bucket should be Monday 2026-04-27.
    assert _bucket_start(date(2026, 4, 29), "week") == date(2026, 4, 27)


def test_bucket_start_month_and_year() -> None:
    assert _bucket_start(date(2026, 4, 29), "month") == date(2026, 4, 1)
    assert _bucket_start(date(2026, 4, 29), "year") == date(2026, 1, 1)


def test_bucket_start_meteorological_seasons() -> None:
    # Winter spans Dec-Feb and the bucket key is the December of the start year.
    assert _bucket_start(date(2026, 1, 15), "season") == date(2025, 12, 1)
    assert _bucket_start(date(2025, 12, 15), "season") == date(2025, 12, 1)
    assert _bucket_start(date(2026, 4, 1), "season") == date(2026, 3, 1)
    assert _bucket_start(date(2026, 7, 1), "season") == date(2026, 6, 1)
    assert _bucket_start(date(2026, 10, 1), "season") == date(2026, 9, 1)


def test_collapse_to_average_means_across_sources() -> None:
    rows = [
        {"time": date(2026, 4, 1), "location_id": 1, "source": "open_meteo",
         "temp_avg": 10.0, "precipitation": 2.0},
        {"time": date(2026, 4, 1), "location_id": 1, "source": "nasa_power",
         "temp_avg": 12.0, "precipitation": None},
        {"time": date(2026, 4, 2), "location_id": 1, "source": "open_meteo",
         "temp_avg": None, "precipitation": 5.0},
    ]
    out = collapse_to_average(rows, ["temp_avg", "precipitation"])
    by_day = {r["time"]: r for r in out}

    assert by_day[date(2026, 4, 1)]["source"] == "average"
    assert by_day[date(2026, 4, 1)]["temp_avg"] == pytest.approx(11.0)
    # Only one source had a precipitation value — average over present sources.
    assert by_day[date(2026, 4, 1)]["precipitation"] == pytest.approx(2.0)
    assert by_day[date(2026, 4, 2)]["temp_avg"] is None
    assert by_day[date(2026, 4, 2)]["precipitation"] == pytest.approx(5.0)


def test_aggregate_buckets_day_passthrough_sorted() -> None:
    rows = [
        {"time": date(2026, 4, 2), "location_id": 1, "source": "open_meteo", "temp_avg": 11.0},
        {"time": date(2026, 4, 1), "location_id": 1, "source": "open_meteo", "temp_avg": 10.0},
    ]
    out = aggregate_buckets(rows, ["temp_avg"], "day", "open_meteo")
    assert [r["time"] for r in out] == [date(2026, 4, 1), date(2026, 4, 2)]


def test_aggregate_buckets_month_averages_and_sums() -> None:
    rows = [
        {"time": date(2026, 4, 1), "location_id": 1, "source": "open_meteo",
         "temp_avg": 10.0, "precipitation": 1.0},
        {"time": date(2026, 4, 15), "location_id": 1, "source": "open_meteo",
         "temp_avg": 14.0, "precipitation": 2.5},
        {"time": date(2026, 5, 1), "location_id": 1, "source": "open_meteo",
         "temp_avg": 18.0, "precipitation": 0.0},
    ]
    out = aggregate_buckets(rows, ["temp_avg", "precipitation"], "month", "open_meteo")
    by_month = {r["time"]: r for r in out}

    # April: temp_avg averaged, precipitation summed.
    assert by_month[date(2026, 4, 1)]["temp_avg"] == pytest.approx(12.0)
    assert by_month[date(2026, 4, 1)]["precipitation"] == pytest.approx(3.5)
    # May: single sample.
    assert by_month[date(2026, 5, 1)]["temp_avg"] == pytest.approx(18.0)
    assert by_month[date(2026, 5, 1)]["precipitation"] == pytest.approx(0.0)


def test_aggregate_buckets_handles_all_none() -> None:
    rows = [
        {"time": date(2026, 4, 1), "location_id": 1, "source": "open_meteo",
         "temp_avg": None, "precipitation": None},
        {"time": date(2026, 4, 2), "location_id": 1, "source": "open_meteo",
         "temp_avg": None, "precipitation": None},
    ]
    out = aggregate_buckets(rows, ["temp_avg", "precipitation"], "month", "open_meteo")
    assert len(out) == 1
    assert out[0]["temp_avg"] is None
    assert out[0]["precipitation"] is None


def test_aggregate_buckets_separates_locations() -> None:
    rows = [
        {"time": date(2026, 4, 1), "location_id": 1, "source": "open_meteo", "temp_avg": 10.0},
        {"time": date(2026, 4, 1), "location_id": 2, "source": "open_meteo", "temp_avg": 20.0},
    ]
    out = aggregate_buckets(rows, ["temp_avg"], "month", "open_meteo")
    assert len(out) == 2
    by_loc = {r["location_id"]: r["temp_avg"] for r in out}
    assert by_loc[1] == pytest.approx(10.0)
    assert by_loc[2] == pytest.approx(20.0)


@pytest.fixture
def client(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_query(_session, **kwargs):
        captured.update(kwargs)
        return [
            {
                "time": date(2026, 4, 1),
                "location_id": 1,
                "source": "average",
                "temp_avg": 11.0,
            }
        ]

    monkeypatch.setattr(weather_api.query_service, "query_daily", fake_query)

    async def fake_user() -> User:
        return User(id=1, username="admin", password_hash="x")

    async def fake_db() -> AsyncIterator[None]:
        yield None

    app.dependency_overrides[get_current_user] = fake_user
    app.dependency_overrides[get_db] = fake_db

    with TestClient(app) as c:
        yield c, captured

    app.dependency_overrides.clear()


def test_endpoint_passes_params_and_returns_rows(client) -> None:
    c, captured = client
    response = c.get(
        "/api/weather/daily",
        params=[
            ("location_ids", 1),
            ("location_ids", 2),
            ("parameters", "temp_avg"),
            ("parameters", "precipitation"),
            ("date_from", "2026-01-01"),
            ("date_to", "2026-04-30"),
            ("source", "average"),
            ("aggregation", "month"),
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert body == [
        {
            "time": "2026-04-01",
            "location_id": 1,
            "source": "average",
            "temp_avg": 11.0,
        }
    ]
    assert captured["location_ids"] == [1, 2]
    assert captured["parameters"] == ["temp_avg", "precipitation"]
    assert captured["date_from"] == date(2026, 1, 1)
    assert captured["date_to"] == date(2026, 4, 30)
    assert captured["source"] == "average"
    assert captured["aggregation"] == "month"


def test_endpoint_validates_source_enum(client) -> None:
    c, _ = client
    response = c.get(
        "/api/weather/daily",
        params=[
            ("location_ids", 1),
            ("parameters", "temp_avg"),
            ("date_from", "2026-01-01"),
            ("date_to", "2026-04-30"),
            ("source", "garbage"),
        ],
    )
    assert response.status_code == 422


def test_endpoint_propagates_value_error_as_400(client, monkeypatch) -> None:
    c, _ = client

    async def boom(*_args, **_kwargs):
        raise ValueError("Unknown parameters: ['nope']")

    monkeypatch.setattr(weather_api.query_service, "query_daily", boom)
    response = c.get(
        "/api/weather/daily",
        params=[
            ("location_ids", 1),
            ("parameters", "nope"),
            ("date_from", "2026-01-01"),
            ("date_to", "2026-04-30"),
        ],
    )
    assert response.status_code == 400
    assert "Unknown parameters" in response.json()["detail"]
