"""Read-side query service for `weather_daily`.

Supports per-source reads and on-the-fly cross-source averaging, plus
period aggregation (day / week / month / season / year). Aggregation logic
is implemented in pure helpers so it can be unit-tested without a database.

Aggregation rules per parameter:
* Cumulative parameters (precipitation, et0, sunshine_hours, frost_hours)
  are summed across the bucket.
* Everything else is averaged across the bucket.
* When `source=average`, source-level values are first collapsed to a
  per-day mean across the available sources, then bucketed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WeatherDaily
from app.schemas.weather import ALLOWED_PARAMETERS, SUM_PARAMETERS, Aggregation, WeatherSource


def _bucket_start(d: date, agg: Aggregation) -> date:
    if agg == "day":
        return d
    if agg == "week":
        return d - timedelta(days=d.weekday())
    if agg == "month":
        return d.replace(day=1)
    if agg == "year":
        return d.replace(month=1, day=1)
    if agg == "season":
        m = d.month
        if m == 12:
            return date(d.year, 12, 1)
        if m in (1, 2):
            return date(d.year - 1, 12, 1)
        if m in (3, 4, 5):
            return date(d.year, 3, 1)
        if m in (6, 7, 8):
            return date(d.year, 6, 1)
        return date(d.year, 9, 1)
    raise ValueError(f"Unknown aggregation: {agg}")


def _validate_parameters(parameters: Sequence[str]) -> list[str]:
    if not parameters:
        raise ValueError("At least one parameter is required")
    invalid = [p for p in parameters if p not in ALLOWED_PARAMETERS]
    if invalid:
        raise ValueError(f"Unknown parameters: {invalid}")
    # de-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for p in parameters:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def collapse_to_average(
    rows: Iterable[dict[str, Any]], parameters: Sequence[str]
) -> list[dict[str, Any]]:
    """Collapse multi-source rows into per-day cross-source means.

    Output rows carry ``source="average"`` and one entry per (time, location_id).
    Parameters that are ``None`` in every source for a given day stay ``None``.
    """
    groups: dict[tuple[date, int], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in rows:
        key = (r["time"], r["location_id"])
        for p in parameters:
            v = r.get(p)
            if v is not None:
                groups[key][p].append(float(v))

    out: list[dict[str, Any]] = []
    for (t, lid), pvals in groups.items():
        row: dict[str, Any] = {"time": t, "location_id": lid, "source": "average"}
        for p in parameters:
            vals = pvals.get(p, [])
            row[p] = sum(vals) / len(vals) if vals else None
        out.append(row)
    return out


def aggregate_buckets(
    rows: Iterable[dict[str, Any]],
    parameters: Sequence[str],
    aggregation: Aggregation,
    out_source: str,
) -> list[dict[str, Any]]:
    """Group day-level rows into period buckets and aggregate parameters.

    Cumulative parameters (`SUM_PARAMETERS`) are summed; the rest are averaged.
    A bucket with no values for a parameter yields ``None``.
    """
    if aggregation == "day":
        return sorted(rows, key=lambda r: (r["location_id"], r["time"]))

    buckets: dict[tuple[date, int], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in rows:
        bk = (_bucket_start(r["time"], aggregation), r["location_id"])
        # Touch the bucket so all-None days still produce an output row.
        _ = buckets[bk]
        for p in parameters:
            v = r.get(p)
            if v is not None:
                buckets[bk][p].append(float(v))

    out: list[dict[str, Any]] = []
    for (t, lid), pvals in buckets.items():
        row: dict[str, Any] = {"time": t, "location_id": lid, "source": out_source}
        for p in parameters:
            vals = pvals.get(p, [])
            if not vals:
                row[p] = None
            elif p in SUM_PARAMETERS:
                row[p] = sum(vals)
            else:
                row[p] = sum(vals) / len(vals)
        out.append(row)
    return sorted(out, key=lambda r: (r["location_id"], r["time"]))


async def query_daily(
    session: AsyncSession,
    *,
    location_ids: Sequence[int],
    parameters: Sequence[str],
    date_from: date,
    date_to: date,
    source: WeatherSource,
    aggregation: Aggregation,
) -> list[dict[str, Any]]:
    """Fetch rows from `weather_daily`, optionally average across sources, then bucket."""
    if not location_ids:
        raise ValueError("At least one location_id is required")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    parameters = _validate_parameters(parameters)

    cols = [WeatherDaily.time, WeatherDaily.location_id, WeatherDaily.source]
    cols.extend(getattr(WeatherDaily, p) for p in parameters)
    stmt = select(*cols).where(
        WeatherDaily.location_id.in_(list(location_ids)),
        WeatherDaily.time >= date_from,
        WeatherDaily.time <= date_to,
    )
    if source != "average":
        stmt = stmt.where(WeatherDaily.source == source)

    result = await session.execute(stmt)
    raw: list[dict[str, Any]] = [
        {
            "time": row.time,
            "location_id": row.location_id,
            "source": row.source,
            **{p: getattr(row, p) for p in parameters},
        }
        for row in result.all()
    ]

    if source == "average":
        raw = collapse_to_average(raw, parameters)
        out_source = "average"
    else:
        out_source = source

    return aggregate_buckets(raw, parameters, aggregation, out_source)
