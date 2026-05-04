"""OpenWeatherMap client (optional source).

Free-tier endpoints used:
  * current weather  — `/data/2.5/weather`
  * 5-day / 3-hour forecast — `/data/2.5/forecast`

Free-tier limit is 60 requests / minute. An in-process token bucket
(`_rate_limit`) enforces a 1-second minimum between requests so concurrent
callers never exceed the quota.

Activation: the client is enabled only when `OPENWEATHERMAP_API_KEY` is set in
the environment. `is_configured()` exposes that check; calling `fetch_*` with
no key raises `OpenWeatherMapNotConfigured`.
"""

from __future__ import annotations

import asyncio
import math
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.services.weather.dto import WeatherDailyDTO

logger = structlog.get_logger(__name__)

CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
SOURCE = "openweathermap"

_REQUEST_TIMEOUT = httpx.Timeout(30.0)

# Free tier: 60 req/min.
_FREE_TIER_PER_MIN = 60
_MIN_INTERVAL_SEC = 60.0 / _FREE_TIER_PER_MIN

_rate_lock = asyncio.Lock()
_last_request_at: float = 0.0


class OpenWeatherMapNotConfiguredError(RuntimeError):
    """Raised when the OpenWeatherMap API key is not configured."""


def is_configured() -> bool:
    """Return True if the OpenWeatherMap API key is set in env."""
    return bool(get_settings().OPENWEATHERMAP_API_KEY)


def _api_key() -> str:
    key = get_settings().OPENWEATHERMAP_API_KEY
    if not key:
        raise OpenWeatherMapNotConfiguredError(
            "OPENWEATHERMAP_API_KEY is not set; client disabled."
        )
    return key


def _make_client() -> httpx.AsyncClient:
    """Factory wrapped for test injection (monkeypatch this in tests)."""
    return httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)


async def _rate_limit() -> None:
    global _last_request_at
    async with _rate_lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL_SEC - (now - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_at = time.monotonic()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _fetch(url: str, params: dict[str, Any]) -> dict[str, Any]:
    await _rate_limit()
    redacted = {k: ("***" if k == "appid" else v) for k, v in params.items()}
    logger.info("openweathermap_request", url=url, params=redacted)
    async with _make_client() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _calc_vpd(temp_c: float | None, rh_pct: float | None) -> float | None:
    """Tetens formula: VPD (kPa) from air temperature (°C) and RH (%)."""
    if temp_c is None or rh_pct is None:
        return None
    es = 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))
    return round(es * (1 - rh_pct / 100), 4)


def _avg(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None


def _safe_min(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return min(nums) if nums else None


def _safe_max(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return max(nums) if nums else None


def _frost_entries(temps: list[float | None]) -> int:
    return sum(1 for t in temps if t is not None and t < 0)


async def fetch_current(
    lat: float,
    lon: float,
    *,
    location_id: int | None = None,
) -> WeatherDailyDTO:
    """Fetch current-weather snapshot at (lat, lon).

    Returns a single `WeatherDailyDTO` stamped with the snapshot's UTC date.
    Daily-aggregate fields not present in a single snapshot (et0,
    sunshine_hours, frost_hours, soil_*) are left as `None`.
    """
    params: dict[str, Any] = {
        "lat": lat,
        "lon": lon,
        "appid": _api_key(),
        "units": "metric",
    }
    payload = await _fetch(CURRENT_URL, params)

    main = payload.get("main") or {}
    wind = payload.get("wind") or {}
    rain = payload.get("rain") or {}
    snow = payload.get("snow") or {}

    ts = payload.get("dt")
    d = datetime.fromtimestamp(ts, tz=UTC).date() if ts else date.today()

    temp = main.get("temp")
    humidity = main.get("humidity")
    precipitation = (rain.get("1h") or rain.get("3h") or 0.0) + (
        snow.get("1h") or snow.get("3h") or 0.0
    )

    dto = WeatherDailyDTO(
        time=d,
        source=SOURCE,
        location_id=location_id,
        temp_min=main.get("temp_min"),
        temp_max=main.get("temp_max"),
        temp_avg=temp,
        humidity_avg=humidity,
        precipitation=precipitation,
        wind_speed_avg=wind.get("speed"),
        wind_speed_max=wind.get("gust"),
        vpd=_calc_vpd(temp, humidity),
    )
    logger.info(
        "openweathermap_current_loaded",
        lat=lat,
        lon=lon,
        date=d.isoformat(),
    )
    return dto


async def fetch_forecast(
    lat: float,
    lon: float,
    *,
    location_id: int | None = None,
) -> list[WeatherDailyDTO]:
    """Fetch 5-day / 3-hour forecast and aggregate to daily DTOs."""
    params: dict[str, Any] = {
        "lat": lat,
        "lon": lon,
        "appid": _api_key(),
        "units": "metric",
    }
    payload = await _fetch(FORECAST_URL, params)
    items: list[dict[str, Any]] = payload.get("list") or []

    by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        ts = item.get("dt")
        if ts is None:
            continue
        d = datetime.fromtimestamp(ts, tz=UTC).date()
        by_day[d].append(item)

    out: list[WeatherDailyDTO] = []
    for d in sorted(by_day.keys()):
        entries = by_day[d]
        temps = [(e.get("main") or {}).get("temp") for e in entries]
        temp_mins = [(e.get("main") or {}).get("temp_min") for e in entries]
        temp_maxs = [(e.get("main") or {}).get("temp_max") for e in entries]
        humidities = [(e.get("main") or {}).get("humidity") for e in entries]
        winds = [(e.get("wind") or {}).get("speed") for e in entries]
        gusts = [(e.get("wind") or {}).get("gust") for e in entries]
        # Each forecast bucket spans 3 hours; sum rain + snow for daily total.
        precip_total = 0.0
        for e in entries:
            r = e.get("rain") or {}
            s = e.get("snow") or {}
            precip_total += float(r.get("3h") or 0.0) + float(s.get("3h") or 0.0)

        temp_avg = _avg(temps)
        humidity_avg = _avg(humidities)
        out.append(
            WeatherDailyDTO(
                time=d,
                source=SOURCE,
                location_id=location_id,
                temp_min=_safe_min(temp_mins) or _safe_min(temps),
                temp_max=_safe_max(temp_maxs) or _safe_max(temps),
                temp_avg=temp_avg,
                humidity_min=_safe_min(humidities),
                humidity_max=_safe_max(humidities),
                humidity_avg=humidity_avg,
                # Each entry covers a 3-hour bucket.
                frost_hours=_frost_entries(temps) * 3,
                precipitation=precip_total,
                wind_speed_avg=_avg(winds),
                wind_speed_max=_safe_max([*gusts, *winds]),
                vpd=_calc_vpd(temp_avg, humidity_avg),
            )
        )
    logger.info(
        "openweathermap_forecast_loaded",
        lat=lat,
        lon=lon,
        days=len(out),
    )
    return out
