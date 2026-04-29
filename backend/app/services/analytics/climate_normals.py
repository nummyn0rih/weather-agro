"""Climate normals: multi-year mean/std/min/max per period bucket.

A climate normal is the long-run statistic of a weather parameter inside a
fixed calendar bucket (e.g. April → mean temp_avg over every available year).
The unified `weather_daily` cross-source average is used as the input series
so normals do not double-count the same date when several sources cover it.

`calculate_normals` is the read-time computation; results are persisted into
the `climate_normals` table by `recompute_normals_for_location`. The monthly
APScheduler job (1st of month) calls `recompute_all` to refresh every
(location, parameter, period) combination supported by the system.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import date, datetime, timezone
from typing import Any

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ClimateNormal, Location, WeatherDaily
from app.schemas.analytics import NormalPeriod
from app.schemas.weather import ALLOWED_PARAMETERS
from app.services.weather.query import collapse_to_average

logger = structlog.get_logger(__name__)

# Parameters that have a numeric meaning when averaged across years. Excludes
# `frost_hours` (integer count) only by convention; it's still allowed here.
NORMAL_PARAMETERS: tuple[str, ...] = (
    "temp_min",
    "temp_max",
    "temp_avg",
    "humidity_avg",
    "precipitation",
    "et0",
    "solar_radiation",
    "sunshine_hours",
    "wind_speed_avg",
    "vpd",
)

NORMAL_PERIODS: tuple[NormalPeriod, ...] = ("month", "week", "doy")


def _bucket_for(d: date, period: NormalPeriod) -> int:
    if period == "month":
        return d.month
    if period == "week":
        return d.isocalendar().week
    if period == "doy":
        return d.timetuple().tm_yday
    raise ValueError(f"Unknown period: {period}")


def _stats(values: Sequence[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "std": None, "min": None, "max": None}
    n = len(values)
    mean = sum(values) / n
    if n > 1:
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        std = math.sqrt(var)
    else:
        std = 0.0
    return {"mean": mean, "std": std, "min": min(values), "max": max(values)}


def compute_normals_from_rows(
    rows: Iterable[dict[str, Any]],
    *,
    location_id: int,
    parameter: str,
    period: NormalPeriod,
) -> list[dict[str, Any]]:
    """Pure aggregator: collapse per-day rows into per-bucket statistics.

    Input rows must be already collapsed to one row per (date, location_id);
    rows whose `parameter` is `None` are skipped, but the bucket is touched
    so empty buckets surface with `count=0`.
    """
    by_bucket: dict[int, list[float]] = defaultdict(list)
    years_present: dict[int, set[int]] = defaultdict(set)
    for r in rows:
        d: date = r["time"]
        b = _bucket_for(d, period)
        years_present[b].add(d.year)
        v = r.get(parameter)
        if v is not None:
            by_bucket[b].append(float(v))

    out: list[dict[str, Any]] = []
    all_buckets = set(by_bucket) | set(years_present)
    for b in sorted(all_buckets):
        vals = by_bucket.get(b, [])
        years = years_present.get(b, set())
        stats = _stats(vals)
        out.append(
            {
                "location_id": location_id,
                "parameter": parameter,
                "period": period,
                "bucket": b,
                "mean": stats["mean"],
                "std": stats["std"],
                "min": stats["min"],
                "max": stats["max"],
                "count": len(vals),
                "year_from": min(years) if years else None,
                "year_to": max(years) if years else None,
            }
        )
    return out


async def _fetch_daily_for_normals(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
) -> list[dict[str, Any]]:
    """Fetch all (time, source) rows for a parameter and collapse to source='average'."""
    cols = [
        WeatherDaily.time,
        WeatherDaily.location_id,
        WeatherDaily.source,
        getattr(WeatherDaily, parameter),
    ]
    stmt = select(*cols).where(WeatherDaily.location_id == location_id)
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
    return collapse_to_average(raw, [parameter])


async def calculate_normals(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
    period: NormalPeriod = "month",
) -> list[dict[str, Any]]:
    """Compute climate normals across all available years for one (location, parameter)."""
    if parameter not in ALLOWED_PARAMETERS:
        raise ValueError(f"Unknown parameter: {parameter}")
    if period not in NORMAL_PERIODS:
        raise ValueError(f"Unknown period: {period}")

    rows = await _fetch_daily_for_normals(
        session, location_id=location_id, parameter=parameter
    )
    return compute_normals_from_rows(
        rows, location_id=location_id, parameter=parameter, period=period
    )


async def get_cached_normals(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
    period: NormalPeriod = "month",
) -> list[ClimateNormal]:
    """Read cached rows from `climate_normals` (no recompute)."""
    stmt = (
        select(ClimateNormal)
        .where(
            ClimateNormal.location_id == location_id,
            ClimateNormal.parameter == parameter,
            ClimateNormal.period == period,
        )
        .order_by(ClimateNormal.bucket)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert_normals(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
    period: NormalPeriod,
    rows: Sequence[dict[str, Any]],
) -> int:
    """Replace cached normals for one (location, parameter, period) atomically."""
    await session.execute(
        delete(ClimateNormal).where(
            ClimateNormal.location_id == location_id,
            ClimateNormal.parameter == parameter,
            ClimateNormal.period == period,
        )
    )
    now = datetime.now(timezone.utc)
    for r in rows:
        session.add(
            ClimateNormal(
                location_id=r["location_id"],
                parameter=r["parameter"],
                period=r["period"],
                bucket=r["bucket"],
                mean=r["mean"],
                std=r["std"],
                min=r["min"],
                max=r["max"],
                count=r["count"],
                year_from=r["year_from"],
                year_to=r["year_to"],
                updated_at=now,
            )
        )
    await session.commit()
    return len(rows)


async def recompute_normals_for_location(
    session: AsyncSession,
    *,
    location_id: int,
    parameters: Sequence[str] = NORMAL_PARAMETERS,
    periods: Sequence[NormalPeriod] = NORMAL_PERIODS,
) -> int:
    """Recompute and persist normals for every (parameter, period) at one location."""
    written = 0
    for parameter in parameters:
        for period in periods:
            rows = await calculate_normals(
                session,
                location_id=location_id,
                parameter=parameter,
                period=period,
            )
            written += await upsert_normals(
                session,
                location_id=location_id,
                parameter=parameter,
                period=period,
                rows=rows,
            )
    return written


async def recompute_all(session: AsyncSession) -> int:
    """Recompute normals for every location currently in the DB.

    Returns total number of bucket rows written. Per-location failures are
    swallowed and logged so one bad location does not abort the run.
    """
    result = await session.execute(select(Location.id))
    location_ids = list(result.scalars().all())

    total = 0
    for lid in location_ids:
        try:
            total += await recompute_normals_for_location(session, location_id=lid)
        except Exception:
            logger.exception("climate_normals.recompute_failed", location_id=lid)
    return total
