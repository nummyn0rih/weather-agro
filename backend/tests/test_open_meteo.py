import math
from datetime import date

import httpx
import pytest
from tenacity import wait_none

from app.services.weather import open_meteo

_HISTORICAL_PAYLOAD = {
    "daily": {
        "time": ["2026-04-01", "2026-04-02"],
        "temperature_2m_max": [12.0, 14.0],
        "temperature_2m_min": [2.0, -1.0],
        "temperature_2m_mean": [7.0, 6.0],
        "precipitation_sum": [0.0, 5.4],
        "shortwave_radiation_sum": [12.0, 8.0],
        "et0_fao_evapotranspiration": [3.1, 2.8],
        "wind_speed_10m_max": [4.0, 6.0],
        "sunshine_duration": [36000.0, 18000.0],
    },
    "hourly": {
        "time": [
            "2026-04-01T00:00",
            "2026-04-01T12:00",
            "2026-04-02T00:00",
            "2026-04-02T12:00",
        ],
        "temperature_2m": [-2.0, 8.0, -3.0, 5.0],
        "relative_humidity_2m": [80, 60, 70, 50],
        "dew_point_2m": [-1.0, 0.0, -2.0, -1.0],
        "wind_speed_10m": [3.0, 5.0, 4.0, 8.0],
        "soil_temperature_0_to_7cm": [1.0, 3.0, 0.0, 2.0],
        "soil_temperature_7_to_28cm": [2.0, 4.0, 1.0, 3.0],
        "soil_temperature_28_to_100cm": [5.0, 5.0, 5.0, 5.0],
        "soil_moisture_0_to_7cm": [0.30, 0.32, 0.31, 0.30],
        "soil_moisture_7_to_28cm": [0.25, 0.27, 0.26, 0.25],
        "soil_moisture_28_to_100cm": [0.20, 0.21, 0.20, 0.20],
    },
}

_FORECAST_PAYLOAD = {
    "daily": {
        "time": ["2026-05-01"],
        "temperature_2m_max": [20.0],
        "temperature_2m_min": [10.0],
        "temperature_2m_mean": [15.0],
        "precipitation_sum": [0.0],
        "shortwave_radiation_sum": [25.0],
        "et0_fao_evapotranspiration": [4.0],
        "wind_speed_10m_max": [3.0],
        "sunshine_duration": [3600.0],
    },
    "hourly": {
        "time": ["2026-05-01T00:00", "2026-05-01T12:00"],
        "temperature_2m": [10.0, 20.0],
        "relative_humidity_2m": [80, 50],
        "dew_point_2m": [5.0, 9.0],
        "wind_speed_10m": [2.0, 4.0],
    },
}


def _install_mock_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(5.0))

    monkeypatch.setattr(open_meteo, "_make_client", factory)


def test_calc_vpd_known_values() -> None:
    # T=20°C, RH=50%: es ≈ 2.339 kPa, VPD ≈ 1.169 kPa
    assert open_meteo._calc_vpd(20.0, 50.0) == pytest.approx(1.169, abs=0.01)
    # full saturation -> VPD = 0
    assert open_meteo._calc_vpd(15.0, 100.0) == pytest.approx(0.0, abs=1e-6)
    # missing inputs -> None
    assert open_meteo._calc_vpd(None, 50.0) is None
    assert open_meteo._calc_vpd(20.0, None) is None


async def test_fetch_historical_parses_payload(monkeypatch) -> None:
    captured: dict[str, str | dict[str, str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url).split("?")[0]
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_HISTORICAL_PAYLOAD)

    _install_mock_transport(monkeypatch, handler)

    out = await open_meteo.fetch_historical(
        45.0, 39.0, date(2026, 4, 1), date(2026, 4, 2), location_id=7
    )

    assert captured["url"] == open_meteo.ARCHIVE_URL
    assert captured["params"]["start_date"] == "2026-04-01"
    assert captured["params"]["end_date"] == "2026-04-02"
    assert captured["params"]["wind_speed_unit"] == "ms"

    assert len(out) == 2
    d1, d2 = out

    assert d1.time == date(2026, 4, 1)
    assert d1.source == "open_meteo"
    assert d1.location_id == 7
    assert d1.temp_min == 2.0
    assert d1.temp_max == 12.0
    assert d1.temp_avg == 7.0
    assert d1.precipitation == 0.0
    assert d1.et0 == 3.1
    assert d1.solar_radiation == 12.0
    assert d1.wind_speed_max == 4.0
    assert d1.sunshine_hours == 10.0  # 36000 s -> 10 h
    assert d1.frost_hours == 1  # one of two hours below 0°C

    assert d1.humidity_min == 60
    assert d1.humidity_max == 80
    assert d1.humidity_avg == pytest.approx(70.0)

    assert d1.soil_temp_0 == pytest.approx(2.0)
    assert d1.soil_temp_7 == pytest.approx(2.0)
    assert d1.soil_temp_28 == pytest.approx(3.0)
    assert d1.soil_temp_100 == pytest.approx(5.0)
    assert d1.soil_moisture_0_7 == pytest.approx(0.31)
    assert d1.wind_speed_avg == pytest.approx(4.0)
    assert d1.dew_point == pytest.approx(-0.5)

    expected_es = 0.6108 * math.exp(17.27 * 7 / (7 + 237.3))
    assert d1.vpd == pytest.approx(expected_es * 0.30, rel=1e-3)

    assert d2.time == date(2026, 4, 2)
    assert d2.frost_hours == 1


async def test_fetch_forecast_uses_forecast_url(monkeypatch) -> None:
    captured: dict[str, str | dict[str, str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url).split("?")[0]
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_FORECAST_PAYLOAD)

    _install_mock_transport(monkeypatch, handler)

    out = await open_meteo.fetch_forecast(45.0, 39.0, days=1, location_id=3)

    assert captured["url"] == open_meteo.FORECAST_URL
    assert captured["params"]["forecast_days"] == "1"
    assert len(out) == 1
    row = out[0]
    assert row.source == "open_meteo"
    assert row.location_id == 3
    assert row.temp_max == 20.0
    assert row.temp_avg == 15.0
    assert row.sunshine_hours == 1.0
    assert row.frost_hours == 0
    assert row.vpd is not None


async def test_fetch_retries_on_transport_error(monkeypatch) -> None:
    # Skip backoff sleeps in the retry test.
    monkeypatch.setattr(open_meteo._fetch.retry, "wait", wait_none())

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("simulated")
        return httpx.Response(200, json={"daily": {"time": []}})

    _install_mock_transport(monkeypatch, handler)

    out = await open_meteo.fetch_historical(
        0.0, 0.0, date(2026, 1, 1), date(2026, 1, 1)
    )

    assert calls["n"] == 3
    assert out == []


async def test_fetch_raises_after_max_attempts(monkeypatch) -> None:
    monkeypatch.setattr(open_meteo._fetch.retry, "wait", wait_none())

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="upstream down")

    _install_mock_transport(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await open_meteo.fetch_historical(
            0.0, 0.0, date(2026, 1, 1), date(2026, 1, 1)
        )

    assert calls["n"] == 3
