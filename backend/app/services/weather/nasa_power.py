"""NASA POWER client: daily historical data (AG community).

Used for cross-validation against the primary Open-Meteo source. NASA POWER
exposes a single daily endpoint per point; many of the agro-soil parameters
that Open-Meteo provides at depth are not available here, so the resulting
`WeatherDailyDTO` rows will have several `None` fields by design.

Docs: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
"""

from __future__ import annotations

import math
from datetime import date
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

DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
SOURCE = "nasa_power"

_REQUEST_TIMEOUT = httpx.Timeout(60.0)

# NASA POWER fill value for missing observations.
_FILL_VALUE = -999.0

# AG community parameter codes we request. Anything not listed here is
# unavailable from NASA POWER and stays None on the DTO.
_PARAMETERS = (
    "T2M_MAX",
    "T2M_MIN",
    "T2M",
    "T2MDEW",
    "RH2M",
    "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN",
    "WS10M",
    "WS10M_MAX",
    "TS",
    "GWETTOP",
    "GWETROOT",
    "GWETPROF",
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
    logger.info("nasa_power_request", url=url, params=params)
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


def _clean(value: Any) -> float | None:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or f <= _FILL_VALUE:
        return None
    return f


def _parse_response(
    payload: dict[str, Any],
    *,
    location_id: int | None,
) -> list[WeatherDailyDTO]:
    parameter = (payload.get("properties") or {}).get("parameter") or {}
    if not parameter:
        return []

    series: dict[str, dict[str, Any]] = {
        name: parameter.get(name) or {} for name in _PARAMETERS
    }

    # All parameters share the same set of date keys; pick from the first
    # non-empty series and sort chronologically.
    day_keys: list[str] = []
    for s in series.values():
        if s:
            day_keys = sorted(s.keys())
            break

    out: list[WeatherDailyDTO] = []
    for key in day_keys:
        d = date(int(key[0:4]), int(key[4:6]), int(key[6:8]))

        temp_avg = _clean(series["T2M"].get(key))
        temp_min = _clean(series["T2M_MIN"].get(key))
        temp_max = _clean(series["T2M_MAX"].get(key))
        humidity_avg = _clean(series["RH2M"].get(key))
        dew_point = _clean(series["T2MDEW"].get(key))
        precipitation = _clean(series["PRECTOTCORR"].get(key))
        # ALLSKY_SFC_SW_DWN reported in kWh/m²/day → convert to MJ/m²/day
        # (×3.6) to match the Open-Meteo unit. NASA returns kWh/m²/day for
        # AG community by default.
        rad_kwh = _clean(series["ALLSKY_SFC_SW_DWN"].get(key))
        solar_radiation = round(rad_kwh * 3.6, 4) if rad_kwh is not None else None
        wind_avg = _clean(series["WS10M"].get(key))
        wind_max = _clean(series["WS10M_MAX"].get(key))
        skin_temp = _clean(series["TS"].get(key))
        soil_m_top = _clean(series["GWETTOP"].get(key))
        soil_m_root = _clean(series["GWETROOT"].get(key))
        soil_m_prof = _clean(series["GWETPROF"].get(key))

        out.append(
            WeatherDailyDTO(
                time=d,
                source=SOURCE,
                location_id=location_id,
                temp_min=temp_min,
                temp_max=temp_max,
                temp_avg=temp_avg,
                # NASA POWER exposes only land-surface skin temperature; map
                # it onto the topmost soil layer and leave deeper layers None.
                soil_temp_0=skin_temp,
                soil_temp_7=None,
                soil_temp_28=None,
                soil_temp_100=None,
                dew_point=dew_point,
                frost_hours=None,
                humidity_min=None,
                humidity_max=None,
                humidity_avg=humidity_avg,
                soil_moisture_0_7=soil_m_top,
                soil_moisture_7_28=soil_m_root,
                soil_moisture_28_100=soil_m_prof,
                precipitation=precipitation,
                et0=None,
                solar_radiation=solar_radiation,
                sunshine_hours=None,
                wind_speed_avg=wind_avg,
                wind_speed_max=wind_max,
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
    """Fetch NASA POWER daily data for the inclusive date range."""
    params: dict[str, Any] = {
        "parameters": ",".join(_PARAMETERS),
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": date_from.strftime("%Y%m%d"),
        "end": date_to.strftime("%Y%m%d"),
        "format": "JSON",
    }
    payload = await _fetch(DAILY_URL, params)
    rows = _parse_response(payload, location_id=location_id)
    logger.info(
        "nasa_power_historical_loaded",
        lat=lat,
        lon=lon,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        rows=len(rows),
    )
    return rows
