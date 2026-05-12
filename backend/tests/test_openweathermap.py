from datetime import UTC, date, datetime

import httpx
import pytest

from app.services.weather import openweathermap

_CURRENT_PAYLOAD = {
    "coord": {"lon": 39.0, "lat": 45.0},
    "weather": [{"main": "Clouds", "description": "broken clouds"}],
    "main": {
        "temp": 8.4,
        "feels_like": 6.0,
        "temp_min": 6.0,
        "temp_max": 10.5,
        "pressure": 1015,
        "humidity": 72,
    },
    "wind": {"speed": 4.2, "gust": 7.1},
    "rain": {"1h": 0.6},
    "dt": int(datetime(2026, 4, 1, 12, 0, tzinfo=UTC).timestamp()),
    "name": "Krasnodar",
}


def _make_forecast_entry(
    dt: datetime,
    *,
    temp: float,
    temp_min: float,
    temp_max: float,
    humidity: float,
    wind_speed: float,
    gust: float | None = None,
    rain_3h: float | None = None,
) -> dict:
    entry: dict = {
        "dt": int(dt.timestamp()),
        "main": {
            "temp": temp,
            "temp_min": temp_min,
            "temp_max": temp_max,
            "humidity": humidity,
        },
        "wind": {"speed": wind_speed},
    }
    if gust is not None:
        entry["wind"]["gust"] = gust
    if rain_3h is not None:
        entry["rain"] = {"3h": rain_3h}
    return entry


_DAY1 = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
_DAY2 = datetime(2026, 4, 2, 0, 0, tzinfo=UTC)

_FORECAST_PAYLOAD = {
    "list": [
        # Day 1: two 3-hour buckets, one freezing.
        _make_forecast_entry(
            _DAY1,
            temp=-2.0,
            temp_min=-3.0,
            temp_max=-1.0,
            humidity=80,
            wind_speed=3.0,
            gust=6.0,
            rain_3h=0.0,
        ),
        _make_forecast_entry(
            _DAY1.replace(hour=3),
            temp=4.0,
            temp_min=3.0,
            temp_max=5.0,
            humidity=70,
            wind_speed=4.0,
            gust=7.0,
            rain_3h=1.2,
        ),
        # Day 2: one bucket above zero.
        _make_forecast_entry(
            _DAY2,
            temp=10.0,
            temp_min=9.0,
            temp_max=11.5,
            humidity=60,
            wind_speed=2.0,
            rain_3h=0.0,
        ),
    ],
    "city": {"coord": {"lat": 45.0, "lon": 39.0}, "name": "Krasnodar"},
}


@pytest.fixture(autouse=True)
def _disable_rate_limiter(monkeypatch) -> None:
    """Tests must not pay the 1s-per-call free-tier interval."""
    monkeypatch.setattr(openweathermap, "_MIN_INTERVAL_SEC", 0.0)
    monkeypatch.setattr(openweathermap, "_last_request_at", 0.0)


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch) -> None:
    """Pretend the operator configured an API key (resolver short-circuit)."""

    async def fake_get_secret(name: str, session=None) -> str | None:
        if name == "openweathermap_api_key":
            return "test-key-123"
        return None

    monkeypatch.setattr(
        openweathermap.settings_resolver, "get_secret", fake_get_secret
    )


def _install_mock_transport(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(5.0))

    monkeypatch.setattr(openweathermap, "_make_client", factory)


def test_calc_vpd_known_values() -> None:
    assert openweathermap._calc_vpd(20.0, 50.0) == pytest.approx(1.169, abs=0.01)
    assert openweathermap._calc_vpd(15.0, 100.0) == pytest.approx(0.0, abs=1e-6)
    assert openweathermap._calc_vpd(None, 50.0) is None
    assert openweathermap._calc_vpd(20.0, None) is None


async def test_is_configured_reflects_api_key(monkeypatch) -> None:
    async def empty(_name: str, session=None) -> str | None:
        return None

    async def present(_name: str, session=None) -> str | None:
        return "abc"

    monkeypatch.setattr(openweathermap.settings_resolver, "get_secret", empty)
    assert await openweathermap.is_configured() is False
    monkeypatch.setattr(openweathermap.settings_resolver, "get_secret", present)
    assert await openweathermap.is_configured() is True


async def test_fetch_current_without_key_raises(monkeypatch) -> None:
    async def empty(_name: str, session=None) -> str | None:
        return None

    monkeypatch.setattr(openweathermap.settings_resolver, "get_secret", empty)
    with pytest.raises(openweathermap.OpenWeatherMapNotConfiguredError):
        await openweathermap.fetch_current(45.0, 39.0)


async def test_fetch_current_parses_payload(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url).split("?")[0]
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_CURRENT_PAYLOAD)

    _install_mock_transport(monkeypatch, handler)

    dto = await openweathermap.fetch_current(45.0, 39.0, location_id=7)

    assert captured["url"] == openweathermap.CURRENT_URL
    assert captured["params"]["appid"] == "test-key-123"
    assert captured["params"]["units"] == "metric"
    assert captured["params"]["lat"] == "45.0"
    assert captured["params"]["lon"] == "39.0"

    assert dto.source == "openweathermap"
    assert dto.location_id == 7
    assert dto.time == date(2026, 4, 1)
    assert dto.temp_avg == 8.4
    assert dto.temp_min == 6.0
    assert dto.temp_max == 10.5
    assert dto.humidity_avg == 72
    assert dto.precipitation == pytest.approx(0.6)
    assert dto.wind_speed_avg == 4.2
    assert dto.wind_speed_max == 7.1
    assert dto.vpd is not None and dto.vpd > 0


async def test_fetch_forecast_aggregates_daily(monkeypatch) -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url).split("?")[0]
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_FORECAST_PAYLOAD)

    _install_mock_transport(monkeypatch, handler)

    out = await openweathermap.fetch_forecast(45.0, 39.0, location_id=7)

    assert captured["url"] == openweathermap.FORECAST_URL
    assert captured["params"]["appid"] == "test-key-123"
    assert len(out) == 2

    d1, d2 = out
    assert d1.time == date(2026, 4, 1)
    assert d1.source == "openweathermap"
    assert d1.location_id == 7
    assert d1.temp_min == -3.0
    assert d1.temp_max == 5.0
    assert d1.temp_avg == pytest.approx(1.0)
    assert d1.humidity_min == 70
    assert d1.humidity_max == 80
    assert d1.humidity_avg == pytest.approx(75.0)
    # One 3-hour bucket below zero -> 3 frost hours.
    assert d1.frost_hours == 3
    assert d1.precipitation == pytest.approx(1.2)
    assert d1.wind_speed_avg == pytest.approx(3.5)
    assert d1.wind_speed_max == 7.0
    assert d1.vpd is not None

    assert d2.time == date(2026, 4, 2)
    assert d2.frost_hours == 0
    assert d2.precipitation == pytest.approx(0.0)
    assert d2.wind_speed_max == 2.0  # no gust -> falls back to wind speed


async def test_fetch_forecast_bins_by_local_tz(monkeypatch) -> None:
    """UTC+3 frost at 02:00 local must land on its local calendar day.

    23:00 UTC on 2026-04-01 is 02:00 Europe/Moscow on 2026-04-02. With
    naive UTC binning the freezing reading filed under Apr 1; ADR-006
    requires it to file under Apr 2 so the alerts engine flags "frost
    on the morning of April 2".
    """
    frost_at_02_local = datetime(2026, 4, 1, 23, 0, tzinfo=UTC)  # 02:00 MSK Apr 2
    warm_midday = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)  # 12:00 MSK Apr 2

    payload = {
        "list": [
            _make_forecast_entry(
                frost_at_02_local,
                temp=-3.0,
                temp_min=-4.0,
                temp_max=-2.0,
                humidity=85,
                wind_speed=2.0,
            ),
            _make_forecast_entry(
                warm_midday,
                temp=10.0,
                temp_min=8.0,
                temp_max=12.0,
                humidity=60,
                wind_speed=3.0,
            ),
        ],
        "city": {"coord": {"lat": 45.0, "lon": 39.0}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _install_mock_transport(monkeypatch, handler)

    out = await openweathermap.fetch_forecast(
        45.0, 39.0, location_id=7, timezone="Europe/Moscow"
    )

    assert len(out) == 1, "both buckets fall on the same local day"
    day = out[0]
    assert day.time == date(2026, 4, 2)
    assert day.frost_hours == 3  # one 3h bucket below zero
    assert day.temp_min == -4.0


async def test_fetch_forecast_utc_default_keeps_legacy_binning(monkeypatch) -> None:
    """Without a `timezone` arg, behaviour matches pre-ADR-006 (UTC)."""
    frost_at_02_local = datetime(2026, 4, 1, 23, 0, tzinfo=UTC)
    warm_midday = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
    payload = {
        "list": [
            _make_forecast_entry(
                frost_at_02_local,
                temp=-3.0,
                temp_min=-4.0,
                temp_max=-2.0,
                humidity=85,
                wind_speed=2.0,
            ),
            _make_forecast_entry(
                warm_midday,
                temp=10.0,
                temp_min=8.0,
                temp_max=12.0,
                humidity=60,
                wind_speed=3.0,
            ),
        ],
        "city": {"coord": {"lat": 45.0, "lon": 39.0}},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _install_mock_transport(monkeypatch, handler)
    out = await openweathermap.fetch_forecast(45.0, 39.0)
    # UTC binning splits the two buckets across two calendar days.
    assert {d.time for d in out} == {date(2026, 4, 1), date(2026, 4, 2)}


async def test_fetch_current_uses_local_tz_for_date(monkeypatch) -> None:
    """23:00 UTC snapshot in UTC+3 stamps the *next* local day."""
    payload = {
        **_CURRENT_PAYLOAD,
        "dt": int(datetime(2026, 4, 1, 23, 0, tzinfo=UTC).timestamp()),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    _install_mock_transport(monkeypatch, handler)

    dto = await openweathermap.fetch_current(
        45.0, 39.0, timezone="Europe/Moscow"
    )
    assert dto.time == date(2026, 4, 2)


async def test_unknown_timezone_falls_back_to_utc(monkeypatch) -> None:
    """Bad TZ names log a warning and bin by UTC instead of crashing."""
    warnings: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        openweathermap.logger,
        "warning",
        lambda event, **kw: warnings.append((event, kw)),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_FORECAST_PAYLOAD)

    _install_mock_transport(monkeypatch, handler)

    out = await openweathermap.fetch_forecast(45.0, 39.0, timezone="Mars/Olympus_Mons")
    assert out  # did not crash
    assert any(e[0] == "openweathermap_unknown_timezone" for e in warnings)


async def test_fetch_current_redacts_api_key_in_logs(monkeypatch) -> None:
    """The API key must never reach the structlog event stream."""
    captured_log: dict = {}

    def fake_info(event: str, **kwargs):
        captured_log.setdefault("events", []).append((event, kwargs))

    monkeypatch.setattr(openweathermap.logger, "info", fake_info)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_CURRENT_PAYLOAD)

    _install_mock_transport(monkeypatch, handler)

    await openweathermap.fetch_current(45.0, 39.0)

    request_logs = [e for e in captured_log["events"] if e[0] == "openweathermap_request"]
    assert request_logs, "expected at least one request log"
    for _, kwargs in request_logs:
        assert kwargs["params"]["appid"] == "***"
