"""Daily anomalies relative to cached climate normals.

For each day in the requested range we look up the climate-normal bucket
(month / ISO week / day-of-year) for the day and compare the observed value
against `mean ± std`. The deviation is reported in absolute units and in
multiples of σ so the frontend can colour-code rows.

Level thresholds:

* ``none``     — |value − mean| ≤ 1σ (or σ is 0/None / no normal available)
* ``moderate`` — 1σ < |value − mean| ≤ 2σ
* ``extreme``  — |value − mean| > 2σ

The unified `weather_daily` cross-source average is used as the input series
when ``source='average'`` so a single day with multiple sources counts once.
Days that lack a value or a matching climate normal are still emitted with
``level='none'`` and ``deviation=None`` so callers can render gaps.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ClimateNormal, WeatherDaily
from app.schemas.analytics import AnomalyLevel, NormalPeriod
from app.schemas.weather import ALLOWED_PARAMETERS, WeatherSource
from app.services.analytics.climate_normals import _bucket_for
from app.services.weather.query import collapse_to_average


def classify_anomaly(
    value: float | None,
    mean: float | None,
    std: float | None,
) -> tuple[AnomalyLevel, float | None, float | None]:
    """Classify one observation against (mean, std).

    Returns ``(level, deviation, sigma)``:

    * ``deviation`` is ``value - mean`` (signed; can be negative).
    * ``sigma`` is ``deviation / std`` (signed) or ``None`` when σ is
      missing/zero — in that case the level falls back to ``none``.
    """
    if value is None or mean is None:
        return "none", None, None
    deviation = float(value) - float(mean)
    if std is None or std == 0:
        return "none", deviation, None
    sigma = deviation / float(std)
    abs_sigma = abs(sigma)
    if abs_sigma > 2:
        return "extreme", deviation, sigma
    if abs_sigma > 1:
        return "moderate", deviation, sigma
    return "none", deviation, sigma


def compute_anomalies(
    rows: Iterable[dict[str, Any]],
    *,
    normals: Sequence[ClimateNormal] | Sequence[dict[str, Any]],
    parameter: str,
    period: NormalPeriod,
) -> list[dict[str, Any]]:
    """Pure aggregator: pair daily rows with the matching climate-normal bucket.

    ``normals`` may be ORM rows or plain dicts; both ``.bucket`` attribute and
    ``["bucket"]`` lookup are accepted so this helper is reusable in tests
    without DB fixtures.
    """

    def _get(obj: Any, key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    by_bucket: dict[int, dict[str, Any]] = {
        int(_get(n, "bucket")): {
            "mean": _get(n, "mean"),
            "std": _get(n, "std"),
        }
        for n in normals
    }

    out: list[dict[str, Any]] = []
    for r in rows:
        d: date = r["time"]
        bucket = _bucket_for(d, period)
        normal = by_bucket.get(bucket)
        mean = normal["mean"] if normal else None
        std = normal["std"] if normal else None
        value = r.get(parameter)
        level, deviation, sigma = classify_anomaly(value, mean, std)
        out.append(
            {
                "time": d,
                "location_id": r["location_id"],
                "parameter": parameter,
                "value": float(value) if value is not None else None,
                "normal_mean": float(mean) if mean is not None else None,
                "normal_std": float(std) if std is not None else None,
                "deviation": deviation,
                "sigma": sigma,
                "level": level,
                "bucket": bucket,
                "period": period,
            }
        )
    return sorted(out, key=lambda r: (r["location_id"], r["time"]))


async def _fetch_daily_values(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
    date_from: date,
    date_to: date,
    source: WeatherSource,
) -> list[dict[str, Any]]:
    cols = [
        WeatherDaily.time,
        WeatherDaily.location_id,
        WeatherDaily.source,
        getattr(WeatherDaily, parameter),
    ]
    stmt = select(*cols).where(
        WeatherDaily.location_id == location_id,
        WeatherDaily.time >= date_from,
        WeatherDaily.time <= date_to,
    )
    if source != "average":
        stmt = stmt.where(WeatherDaily.source == source)
    result = await session.execute(stmt)
    raw = [
        {
            "time": row.time,
            "location_id": row.location_id,
            "source": row.source,
            parameter: getattr(row, parameter),
        }
        for row in result.all()
    ]
    if source == "average":
        return collapse_to_average(raw, [parameter])
    return raw


async def _fetch_normals(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
    period: NormalPeriod,
) -> list[ClimateNormal]:
    stmt = select(ClimateNormal).where(
        ClimateNormal.location_id == location_id,
        ClimateNormal.parameter == parameter,
        ClimateNormal.period == period,
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_anomalies(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
    date_from: date,
    date_to: date,
    period: NormalPeriod = "month",
    source: WeatherSource = "average",
) -> list[dict[str, Any]]:
    """Fetch daily values and pair them with cached normals to produce anomalies."""
    if parameter not in ALLOWED_PARAMETERS:
        raise ValueError(f"Unknown parameter: {parameter}")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    daily = await _fetch_daily_values(
        session,
        location_id=location_id,
        parameter=parameter,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )
    normals = await _fetch_normals(
        session,
        location_id=location_id,
        parameter=parameter,
        period=period,
    )
    return compute_anomalies(
        daily, normals=normals, parameter=parameter, period=period
    )
