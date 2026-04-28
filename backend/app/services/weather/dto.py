from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class WeatherDailyDTO:
    """Source-agnostic daily weather record produced by external API clients.

    Mirrors the shape of `WeatherDaily` / `WeatherForecast` ORM models so it can be
    persisted with a straightforward dict spread.
    """

    time: date
    source: str
    location_id: int | None = None

    temp_min: float | None = None
    temp_max: float | None = None
    temp_avg: float | None = None
    soil_temp_0: float | None = None
    soil_temp_7: float | None = None
    soil_temp_28: float | None = None
    soil_temp_100: float | None = None
    dew_point: float | None = None
    frost_hours: int | None = None

    humidity_min: float | None = None
    humidity_max: float | None = None
    humidity_avg: float | None = None
    soil_moisture_0_7: float | None = None
    soil_moisture_7_28: float | None = None
    soil_moisture_28_100: float | None = None

    precipitation: float | None = None
    et0: float | None = None

    solar_radiation: float | None = None
    sunshine_hours: float | None = None

    wind_speed_avg: float | None = None
    wind_speed_max: float | None = None

    vpd: float | None = None
