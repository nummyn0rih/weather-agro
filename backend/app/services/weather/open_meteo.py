"""Open-Meteo client: ERA5 archive (history) + Forecast API.

Returns `WeatherDailyDTO` lists ready to be persisted into `weather_daily` /
`weather_forecast` tables. VPD is computed here (Tetens formula) and stored
alongside the source values.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.weather.dto import WeatherDailyDTO

logger = structlog.get_logger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE = "open_meteo"

_REQUEST_TIMEOUT = httpx.Timeout(30.0)

_DAILY_PARAMS = (
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "precipitation_sum",
    "shortwave_radiation_sum",
    "et0_fao_evapotranspiration",
    "wind_speed_10m_max",
    "sunshine_duration",
)

_HOURLY_COMMON = (
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "wind_speed_10m",
)

# ERA5 archive uses depth-range layers.
_HOURLY_ARCHIVE = (
    *_HOURLY_COMMON,
    "soil_temperature_0_to_7cm",
    "soil_temperature_7_to_28cm",
    "soil_temperature_28_to_100cm",
    "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm",
    "soil_moisture_28_to_100cm",
)

# Forecast API exposes point-depth soil values.
_HOURLY_FORECAST = (
    *_HOURLY_COMMON,
    "soil_temperature_0cm",
    "soil_temperature_6cm",
    "soil_temperature_18cm",
    "soil_temperature_54cm",
    "soil_moisture_0_to_1cm",
    "soil_moisture_3_to_9cm",
    "soil_moisture_27_to_81cm",
)


def _make_client() -> httpx.AsyncClient:
    """Factory wrapped for test injection (monkeypatch this in tests)."""
    return httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _fetch(url: str, params: dict[str, Any]) -> dict[str, Any]:
    logger.info("open_meteo_request", url=url, params=params)
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


def _avg(values: Iterable[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None


def _safe_min(values: Iterable[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return min(nums) if nums else None


def _safe_max(values: Iterable[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return max(nums) if nums else None


def _frost_hours(temps: Iterable[float | None]) -> int:
    return sum(1 for t in temps if t is not None and t < 0)


def _group_hourly(
    times: list[str], values: list[float | None]
) -> dict[date, list[float | None]]:
    grouped: dict[date, list[float | None]] = defaultdict(list)
    for t, v in zip(times, values, strict=False):
        grouped[datetime.fromisoformat(t).date()].append(v)
    return grouped


def _parse_response(
    payload: dict[str, Any],
    *,
    is_forecast: bool,
    location_id: int | None,
) -> list[WeatherDailyDTO]:
    daily = payload.get("daily") or {}
    hourly = payload.get("hourly") or {}

    daily_times: list[str] = daily.get("time") or []
    if not daily_times:
        return []

    def daily_col(name: str) -> list[float | None]:
        col = daily.get(name)
        return col if col is not None else [None] * len(daily_times)

    hourly_times: list[str] = hourly.get("time") or []

    def hourly_grouped(name: str) -> dict[date, list[float | None]]:
        col = hourly.get(name)
        if col is None:
            return {}
        return _group_hourly(hourly_times, col)

    temp_2m = hourly_grouped("temperature_2m")
    rh = hourly_grouped("relative_humidity_2m")
    dew = hourly_grouped("dew_point_2m")
    wind = hourly_grouped("wind_speed_10m")

    if is_forecast:
        soil_t0 = hourly_grouped("soil_temperature_0cm")
        soil_t7 = hourly_grouped("soil_temperature_6cm")
        soil_t28 = hourly_grouped("soil_temperature_18cm")
        soil_t100 = hourly_grouped("soil_temperature_54cm")
        soil_m0_7 = hourly_grouped("soil_moisture_0_to_1cm")
        soil_m7_28 = hourly_grouped("soil_moisture_3_to_9cm")
        soil_m28_100 = hourly_grouped("soil_moisture_27_to_81cm")
    else:
        soil_t_top = hourly_grouped("soil_temperature_0_to_7cm")
        soil_t0 = soil_t_top
        soil_t7 = soil_t_top
        soil_t28 = hourly_grouped("soil_temperature_7_to_28cm")
        soil_t100 = hourly_grouped("soil_temperature_28_to_100cm")
        soil_m0_7 = hourly_grouped("soil_moisture_0_to_7cm")
        soil_m7_28 = hourly_grouped("soil_moisture_7_to_28cm")
        soil_m28_100 = hourly_grouped("soil_moisture_28_to_100cm")

    temp_min_col = daily_col("temperature_2m_min")
    temp_max_col = daily_col("temperature_2m_max")
    temp_avg_col = daily_col("temperature_2m_mean")
    precip_col = daily_col("precipitation_sum")
    rad_col = daily_col("shortwave_radiation_sum")
    et0_col = daily_col("et0_fao_evapotranspiration")
    wind_max_col = daily_col("wind_speed_10m_max")
    sunshine_col = daily_col("sunshine_duration")

    out: list[WeatherDailyDTO] = []
    for i, day_str in enumerate(daily_times):
        d = date.fromisoformat(day_str)
        rh_day = rh.get(d, [])
        humidity_avg = _avg(rh_day)
        temp_avg = temp_avg_col[i]
        sunshine = sunshine_col[i]
        sunshine_h = sunshine / 3600 if sunshine is not None else None

        out.append(
            WeatherDailyDTO(
                time=d,
                source=SOURCE,
                location_id=location_id,
                temp_min=temp_min_col[i],
                temp_max=temp_max_col[i],
                temp_avg=temp_avg,
                soil_temp_0=_avg(soil_t0.get(d, [])),
                soil_temp_7=_avg(soil_t7.get(d, [])),
                soil_temp_28=_avg(soil_t28.get(d, [])),
                soil_temp_100=_avg(soil_t100.get(d, [])),
                dew_point=_avg(dew.get(d, [])),
                frost_hours=_frost_hours(temp_2m.get(d, [])),
                humidity_min=_safe_min(rh_day),
                humidity_max=_safe_max(rh_day),
                humidity_avg=humidity_avg,
                soil_moisture_0_7=_avg(soil_m0_7.get(d, [])),
                soil_moisture_7_28=_avg(soil_m7_28.get(d, [])),
                soil_moisture_28_100=_avg(soil_m28_100.get(d, [])),
                precipitation=precip_col[i],
                et0=et0_col[i],
                solar_radiation=rad_col[i],
                sunshine_hours=sunshine_h,
                wind_speed_avg=_avg(wind.get(d, [])),
                wind_speed_max=wind_max_col[i],
                vpd=_calc_vpd(temp_avg, humidity_avg),
            )
        )
    return out


async def fetch_historical(
    lat: float,
    lon: float,
    date_from: date,
    date_to: date,
    *,
    location_id: int | None = None,
) -> list[WeatherDailyDTO]:
    """Fetch ERA5 archive data from Open-Meteo for the inclusive date range."""
    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_from.isoformat(),
        "end_date": date_to.isoformat(),
        "daily": ",".join(_DAILY_PARAMS),
        "hourly": ",".join(_HOURLY_ARCHIVE),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    payload = await _fetch(ARCHIVE_URL, params)
    rows = _parse_response(payload, is_forecast=False, location_id=location_id)
    logger.info(
        "open_meteo_historical_loaded",
        lat=lat,
        lon=lon,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        rows=len(rows),
    )
    return rows


async def fetch_forecast(
    lat: float,
    lon: float,
    days: int = 16,
    *,
    location_id: int | None = None,
) -> list[WeatherDailyDTO]:
    """Fetch forecast (up to 16 days) from Open-Meteo."""
    params: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "forecast_days": days,
        "daily": ",".join(_DAILY_PARAMS),
        "hourly": ",".join(_HOURLY_FORECAST),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    payload = await _fetch(FORECAST_URL, params)
    rows = _parse_response(payload, is_forecast=True, location_id=location_id)
    logger.info(
        "open_meteo_forecast_loaded",
        lat=lat,
        lon=lon,
        days=days,
        rows=len(rows),
    )
    return rows
