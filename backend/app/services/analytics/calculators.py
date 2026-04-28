"""Pure functions for derived agronomy/weather parameters.

These calculators are intentionally side-effect-free: they take primitive
inputs (or simple iterables) and return primitive outputs, so they can be
used both at ingest time (e.g. by `weather` clients to populate `vpd` /
`frost_hours`) and at read time (e.g. by analytics endpoints computing GDD
on-the-fly using the crop's base temperature).
"""

from __future__ import annotations

import math
from collections.abc import Iterable


def calculate_vpd(temp_c: float | None, humidity_pct: float | None) -> float | None:
    """Vapor Pressure Deficit (kPa) from air temperature (°C) and RH (%).

    Uses the Tetens formula for saturation vapor pressure. Returns ``None``
    if either input is missing. Result is rounded to 4 decimal places.
    """
    if temp_c is None or humidity_pct is None:
        return None
    es = 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))
    return round(es * (1 - humidity_pct / 100), 4)


def calculate_gdd(
    temp_min: float | None,
    temp_max: float | None,
    base_temp: float,
) -> float | None:
    """Growing Degree Days for a single day (single-triangulation method).

    GDD = max(0, ((Tmin + Tmax) / 2) - Tbase). Returns ``None`` if either
    temperature bound is missing.
    """
    if temp_min is None or temp_max is None:
        return None
    mean = (temp_min + temp_max) / 2
    return max(0.0, mean - base_temp)


def calculate_frost_hours(hourly_temps: Iterable[float | None]) -> int:
    """Count of hourly temperature samples strictly below 0°C.

    ``None`` samples are skipped. The threshold is strict (`< 0`) so that
    a reading of exactly 0°C does not count as frost.
    """
    return sum(1 for t in hourly_temps if t is not None and t < 0)
