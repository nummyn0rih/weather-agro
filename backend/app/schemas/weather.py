from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

WeatherSource = Literal["open_meteo", "nasa_power", "openweathermap", "average"]
Aggregation = Literal["day", "week", "month", "season", "year"]
HeatmapXAxis = Literal["month", "week", "doy"]
CumulativeParameter = Literal["precipitation", "et0", "sunshine_hours", "gdd"]

ALLOWED_PARAMETERS: frozenset[str] = frozenset(
    {
        "temp_min",
        "temp_max",
        "temp_avg",
        "soil_temp_0",
        "soil_temp_7",
        "soil_temp_28",
        "soil_temp_100",
        "dew_point",
        "frost_hours",
        "humidity_min",
        "humidity_max",
        "humidity_avg",
        "soil_moisture_0_7",
        "soil_moisture_7_28",
        "soil_moisture_28_100",
        "precipitation",
        "et0",
        "solar_radiation",
        "sunshine_hours",
        "wind_speed_avg",
        "wind_speed_max",
        "vpd",
    }
)

SUM_PARAMETERS: frozenset[str] = frozenset(
    {"precipitation", "et0", "sunshine_hours", "frost_hours"}
)


class WeatherDailyPoint(BaseModel):
    """One row of aggregated weather output. Parameter columns are dynamic."""

    model_config = ConfigDict(extra="allow")

    time: date
    location_id: int
    source: str


class HeatmapCell(BaseModel):
    """One cell in a heatmap matrix."""

    location_id: int
    parameter: str
    source: str
    year: int
    x: int
    value: float | None


class CumulativePoint(BaseModel):
    """One day on a cumulative-sum series."""

    time: date
    location_id: int
    source: str
    parameter: str
    daily: float | None
    cumulative: float
