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
from app.schemas.weather import (
    ALLOWED_PARAMETERS,
    SUM_PARAMETERS,
    Aggregation,
    CumulativeParameter,
    HeatmapXAxis,
    StatsAggregation,
    WeatherSource,
)
from app.services.analytics.calculators import calculate_gdd


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


async def _fetch_rows(
    session: AsyncSession,
    *,
    location_ids: Sequence[int],
    parameters: Sequence[str],
    date_from: date,
    date_to: date,
    source: WeatherSource,
) -> list[dict[str, Any]]:
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
    return [
        {
            "time": row.time,
            "location_id": row.location_id,
            "source": row.source,
            **{p: getattr(row, p) for p in parameters},
        }
        for row in result.all()
    ]


async def query_daily(
    session: AsyncSession,
    *,
    location_ids: Sequence[int],
    parameters: Sequence[str],
    date_from: date,
    date_to: date,
    source: WeatherSource,
    aggregation: Aggregation,
    compare_years: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """Fetch rows from `weather_daily`, optionally average across sources, then bucket.

    When ``compare_years`` is provided, ``date_from``/``date_to`` are used as a
    month-day window template applied to each requested year. Each row gains a
    ``year`` field so the frontend can overlay multiple years on a common axis.
    """
    if not location_ids:
        raise ValueError("At least one location_id is required")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    parameters = _validate_parameters(parameters)

    if compare_years:
        deduped_years = sorted({int(y) for y in compare_years})
        out: list[dict[str, Any]] = []
        for year in deduped_years:
            try:
                df = date_from.replace(year=year)
                dt = date_to.replace(year=year)
            except ValueError as exc:
                raise ValueError(f"Invalid date for year {year}: {exc}") from exc
            raw = await _fetch_rows(
                session,
                location_ids=location_ids,
                parameters=parameters,
                date_from=df,
                date_to=dt,
                source=source,
            )
            if source == "average":
                raw = collapse_to_average(raw, parameters)
                out_source = "average"
            else:
                out_source = source
            bucketed = aggregate_buckets(raw, parameters, aggregation, out_source)
            for r in bucketed:
                r["year"] = year
            out.extend(bucketed)
        return out

    raw = await _fetch_rows(
        session,
        location_ids=location_ids,
        parameters=parameters,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )

    if source == "average":
        raw = collapse_to_average(raw, parameters)
        out_source = "average"
    else:
        out_source = source

    return aggregate_buckets(raw, parameters, aggregation, out_source)


def _heatmap_x(d: date, axis: HeatmapXAxis) -> int:
    if axis == "month":
        return d.month
    if axis == "week":
        return d.isocalendar().week
    if axis == "doy":
        return d.timetuple().tm_yday
    raise ValueError(f"Unknown heatmap axis: {axis}")


def build_heatmap(
    rows: Iterable[dict[str, Any]],
    parameter: str,
    axis: HeatmapXAxis,
    out_source: str,
) -> list[dict[str, Any]]:
    """Group day-level rows into a (year, x) matrix for one parameter.

    Cumulative parameters are summed inside each cell; everything else is averaged.
    Cells with no values for the parameter yield ``None``.
    """
    cells: dict[tuple[int, int, int], list[float]] = defaultdict(list)
    keys: set[tuple[int, int, int]] = set()
    for r in rows:
        d: date = r["time"]
        key = (r["location_id"], d.year, _heatmap_x(d, axis))
        keys.add(key)
        v = r.get(parameter)
        if v is not None:
            cells[key].append(float(v))

    is_sum = parameter in SUM_PARAMETERS
    out: list[dict[str, Any]] = []
    for key in keys:
        lid, year, x = key
        vals = cells.get(key, [])
        if not vals:
            value: float | None = None
        elif is_sum:
            value = sum(vals)
        else:
            value = sum(vals) / len(vals)
        out.append(
            {
                "location_id": lid,
                "parameter": parameter,
                "source": out_source,
                "year": year,
                "x": x,
                "value": value,
            }
        )
    return sorted(out, key=lambda c: (c["location_id"], c["year"], c["x"]))


async def query_heatmap(
    session: AsyncSession,
    *,
    location_id: int,
    parameter: str,
    date_from: date,
    date_to: date,
    source: WeatherSource,
    axis: HeatmapXAxis,
) -> list[dict[str, Any]]:
    """Heatmap data for a single parameter at a single location."""
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if parameter not in ALLOWED_PARAMETERS:
        raise ValueError(f"Unknown parameter: {parameter}")

    raw = await _fetch_rows(
        session,
        location_ids=[location_id],
        parameters=[parameter],
        date_from=date_from,
        date_to=date_to,
        source=source,
    )
    if source == "average":
        raw = collapse_to_average(raw, [parameter])
        out_source = "average"
    else:
        out_source = source
    return build_heatmap(raw, parameter, axis, out_source)


def build_cumulative(
    rows: Iterable[dict[str, Any]],
    *,
    parameter: CumulativeParameter,
    base_temperature: float | None,
    out_source: str,
) -> list[dict[str, Any]]:
    """Compute a running cumulative series per location.

    ``parameter='gdd'`` derives daily GDD from temp_min/temp_max using
    ``base_temperature``. Other parameters use the matching column directly.
    Missing daily values do not increment the running total.
    """
    by_loc: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_loc[r["location_id"]].append(r)

    out: list[dict[str, Any]] = []
    for lid, lrows in by_loc.items():
        lrows.sort(key=lambda r: r["time"])
        running = 0.0
        for r in lrows:
            if parameter == "gdd":
                if base_temperature is None:
                    raise ValueError("base_temperature is required for parameter='gdd'")
                daily = calculate_gdd(r.get("temp_min"), r.get("temp_max"), base_temperature)
            else:
                v = r.get(parameter)
                daily = float(v) if v is not None else None
            if daily is not None:
                running += daily
            out.append(
                {
                    "time": r["time"],
                    "location_id": lid,
                    "source": out_source,
                    "parameter": parameter,
                    "daily": daily,
                    "cumulative": running,
                }
            )
    return out


def build_stats(
    rows: Iterable[dict[str, Any]],
    parameters: Sequence[str],
    aggregation: StatsAggregation,
    out_source: str,
) -> list[dict[str, Any]]:
    """Group day-level rows into buckets and compute min/max/mean/sum/count per parameter.

    With ``aggregation='total'`` the whole range collapses to one bucket per
    (location, parameter); the bucket's ``time`` is the earliest day seen.
    """

    def bucket_key(d: date) -> date:
        return date(1970, 1, 1) if aggregation == "total" else _bucket_start(
            d, aggregation  # type: ignore[arg-type]
        )

    buckets: dict[
        tuple[date, int, str], dict[str, Any]
    ] = {}
    for r in rows:
        d: date = r["time"]
        bk_date = bucket_key(d)
        for p in parameters:
            key = (bk_date, r["location_id"], p)
            slot = buckets.get(key)
            if slot is None:
                slot = {"values": [], "min_time": d}
                buckets[key] = slot
            else:
                if d < slot["min_time"]:
                    slot["min_time"] = d
            v = r.get(p)
            if v is not None:
                slot["values"].append(float(v))

    out: list[dict[str, Any]] = []
    for (bk_date, lid, p), slot in buckets.items():
        vals: list[float] = slot["values"]
        time_value = slot["min_time"] if aggregation == "total" else bk_date
        if not vals:
            row = {
                "time": time_value,
                "location_id": lid,
                "source": out_source,
                "parameter": p,
                "min": None,
                "max": None,
                "mean": None,
                "sum": None,
                "count": 0,
            }
        else:
            row = {
                "time": time_value,
                "location_id": lid,
                "source": out_source,
                "parameter": p,
                "min": min(vals),
                "max": max(vals),
                "mean": sum(vals) / len(vals),
                "sum": sum(vals),
                "count": len(vals),
            }
        out.append(row)
    return sorted(out, key=lambda r: (r["location_id"], r["parameter"], r["time"]))


async def query_stats(
    session: AsyncSession,
    *,
    location_ids: Sequence[int],
    parameters: Sequence[str],
    date_from: date,
    date_to: date,
    source: WeatherSource,
    aggregation: StatsAggregation,
) -> list[dict[str, Any]]:
    """Aggregated min/max/mean/sum/count per parameter, grouped by aggregation level."""
    if not location_ids:
        raise ValueError("At least one location_id is required")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    parameters = _validate_parameters(parameters)

    raw = await _fetch_rows(
        session,
        location_ids=location_ids,
        parameters=parameters,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )
    if source == "average":
        raw = collapse_to_average(raw, parameters)
        out_source = "average"
    else:
        out_source = source
    return build_stats(raw, parameters, aggregation, out_source)


async def query_cumulative(
    session: AsyncSession,
    *,
    location_ids: Sequence[int],
    parameter: CumulativeParameter,
    date_from: date,
    date_to: date,
    source: WeatherSource,
    base_temperature: float | None = None,
) -> list[dict[str, Any]]:
    """Running cumulative series for precipitation/et0/sunshine_hours/gdd."""
    if not location_ids:
        raise ValueError("At least one location_id is required")
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")
    if parameter == "gdd" and base_temperature is None:
        raise ValueError("base_temperature is required for parameter='gdd'")

    fetch_params: list[str] = (
        ["temp_min", "temp_max"] if parameter == "gdd" else [parameter]
    )
    raw = await _fetch_rows(
        session,
        location_ids=location_ids,
        parameters=fetch_params,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )
    if source == "average":
        raw = collapse_to_average(raw, fetch_params)
        out_source = "average"
    else:
        out_source = source
    return build_cumulative(
        raw,
        parameter=parameter,
        base_temperature=base_temperature,
        out_source=out_source,
    )
