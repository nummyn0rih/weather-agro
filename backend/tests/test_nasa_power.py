import math
from datetime import date

import httpx
import pytest
from tenacity import wait_none

from app.services.weather import nasa_power

_PAYLOAD = {
    "properties": {
        "parameter": {
            "T2M_MAX": {"20260401": 12.0, "20260402": 14.0},
            "T2M_MIN": {"20260401": 2.0, "20260402": -1.0},
            "T2M": {"20260401": 7.0, "20260402": 6.0},
            "T2MDEW": {"20260401": -0.5, "20260402": -1.5},
            "RH2M": {"20260401": 70.0, "20260402": 60.0},
            "PRECTOTCORR": {"20260401": 0.0, "20260402": 5.4},
            "ALLSKY_SFC_SW_DWN": {"20260401": 3.0, "20260402": -999.0},
            "WS10M": {"20260401": 4.0, "20260402": 5.0},
            "WS10M_MAX": {"20260401": 6.0, "20260402": 8.0},
            "TS": {"20260401": 5.0, "20260402": 4.0},
            "GWETTOP": {"20260401": 0.6, "20260402": 0.55},
            "GWETROOT": {"20260401": 0.5, "20260402": 0.5},
            "GWETPROF": {"20260401": 0.4, "20260402": -999.0},
        }
    }
}


def _install_mock_transport(monkeypatch, handler) -> None:
    transport = httpx.MockTransport(handler)

    def factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=transport, timeout=httpx.Timeout(5.0))

    monkeypatch.setattr(nasa_power, "_make_client", factory)


def test_calc_vpd_known_values() -> None:
    assert nasa_power._calc_vpd(20.0, 50.0) == pytest.approx(1.169, abs=0.01)
    assert nasa_power._calc_vpd(15.0, 100.0) == pytest.approx(0.0, abs=1e-6)
    assert nasa_power._calc_vpd(None, 50.0) is None
    assert nasa_power._calc_vpd(20.0, None) is None


def test_clean_filters_fill_value() -> None:
    assert nasa_power._clean(-999.0) is None
    assert nasa_power._clean(-1000.0) is None
    assert nasa_power._clean(None) is None
    assert nasa_power._clean(float("nan")) is None
    assert nasa_power._clean("not a number") is None
    assert nasa_power._clean(7.5) == 7.5


async def test_fetch_historical_parses_payload(monkeypatch) -> None:
    captured: dict[str, str | dict[str, str]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url).split("?")[0]
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=_PAYLOAD)

    _install_mock_transport(monkeypatch, handler)

    out = await nasa_power.fetch_historical(
        45.0, 39.0, date(2026, 4, 1), date(2026, 4, 2), location_id=11
    )

    assert captured["url"] == nasa_power.DAILY_URL
    assert captured["params"]["start"] == "20260401"
    assert captured["params"]["end"] == "20260402"
    assert captured["params"]["community"] == "AG"
    assert captured["params"]["format"] == "JSON"
    assert "T2M" in captured["params"]["parameters"]

    assert len(out) == 2
    d1, d2 = out

    assert d1.time == date(2026, 4, 1)
    assert d1.source == "nasa_power"
    assert d1.location_id == 11
    assert d1.temp_min == 2.0
    assert d1.temp_max == 12.0
    assert d1.temp_avg == 7.0
    assert d1.precipitation == 0.0
    assert d1.humidity_avg == 70.0
    assert d1.dew_point == -0.5
    assert d1.wind_speed_avg == 4.0
    assert d1.wind_speed_max == 6.0
    # 3.0 kWh/m²/day -> 10.8 MJ/m²/day
    assert d1.solar_radiation == pytest.approx(10.8)
    assert d1.soil_temp_0 == 5.0
    assert d1.soil_moisture_0_7 == 0.6
    assert d1.soil_moisture_7_28 == 0.5
    assert d1.soil_moisture_28_100 == 0.4

    # Parameters NASA POWER does not provide must stay None.
    assert d1.soil_temp_7 is None
    assert d1.soil_temp_28 is None
    assert d1.soil_temp_100 is None
    assert d1.frost_hours is None
    assert d1.humidity_min is None
    assert d1.humidity_max is None
    assert d1.et0 is None
    assert d1.sunshine_hours is None

    expected_es = 0.6108 * math.exp(17.27 * 7 / (7 + 237.3))
    assert d1.vpd == pytest.approx(expected_es * 0.30, rel=1e-3)

    # Fill values must be coerced to None.
    assert d2.solar_radiation is None
    assert d2.soil_moisture_28_100 is None


async def test_fetch_historical_empty_payload(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"properties": {"parameter": {}}})

    _install_mock_transport(monkeypatch, handler)

    out = await nasa_power.fetch_historical(
        0.0, 0.0, date(2026, 1, 1), date(2026, 1, 1)
    )
    assert out == []


async def test_fetch_retries_on_transport_error(monkeypatch) -> None:
    monkeypatch.setattr(nasa_power._fetch.retry, "wait", wait_none())

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("simulated")
        return httpx.Response(200, json={"properties": {"parameter": {}}})

    _install_mock_transport(monkeypatch, handler)

    out = await nasa_power.fetch_historical(
        0.0, 0.0, date(2026, 1, 1), date(2026, 1, 1)
    )
    assert calls["n"] == 3
    assert out == []


async def test_fetch_raises_after_max_attempts(monkeypatch) -> None:
    monkeypatch.setattr(nasa_power._fetch.retry, "wait", wait_none())

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="upstream down")

    _install_mock_transport(monkeypatch, handler)

    with pytest.raises(httpx.HTTPStatusError):
        await nasa_power.fetch_historical(
            0.0, 0.0, date(2026, 1, 1), date(2026, 1, 1)
        )
    assert calls["n"] == 3
