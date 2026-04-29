"""Pearson correlation matrix between weather parameters.

Pulls daily values for one location across a date range, optionally collapses
multi-source rows to a per-day cross-source mean, then computes pairwise
Pearson correlation coefficients with NaN-aware pairwise deletion (each cell
uses only days where both parameters have values).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WeatherDaily
from app.schemas.weather import ALLOWED_PARAMETERS, WeatherSource
from app.services.weather.query import collapse_to_average


def compute_correlations(
    rows: Iterable[dict[str, Any]],
    parameters: Sequence[str],
) -> dict[str, Any]:
    """Pure aggregator: NxN Pearson matrix with pairwise NaN deletion.

    Cells where the paired sample has fewer than 2 observations or one of
    the variables has zero variance return ``None``.
    """
    params = list(parameters)
    n = len(params)
    matrix: list[list[float | None]] = [[None] * n for _ in range(n)]
    counts: list[list[int]] = [[0] * n for _ in range(n)]

    rows_list = list(rows)
    if n == 0 or not rows_list:
        return {
            "parameters": params,
            "matrix": matrix,
            "counts": counts,
            "n": len(rows_list),
        }

    arr = np.array(
        [
            [r.get(p) if r.get(p) is not None else np.nan for p in params]
            for r in rows_list
        ],
        dtype=float,
    )

    for i in range(n):
        for j in range(n):
            xi = arr[:, i]
            xj = arr[:, j]
            mask = ~(np.isnan(xi) | np.isnan(xj))
            xi_m = xi[mask]
            xj_m = xj[mask]
            count = int(mask.sum())
            counts[i][j] = count
            if count < 2:
                continue
            std_i = float(np.std(xi_m))
            std_j = float(np.std(xj_m))
            if std_i == 0.0 or std_j == 0.0:
                continue
            coef = float(np.corrcoef(xi_m, xj_m)[0, 1])
            if np.isnan(coef):
                continue
            matrix[i][j] = coef

    return {
        "parameters": params,
        "matrix": matrix,
        "counts": counts,
        "n": int(arr.shape[0]),
    }


def _validate_parameters(parameters: Sequence[str]) -> list[str]:
    if not parameters:
        raise ValueError("At least one parameter is required")
    invalid = [p for p in parameters if p not in ALLOWED_PARAMETERS]
    if invalid:
        raise ValueError(f"Unknown parameters: {invalid}")
    seen: set[str] = set()
    deduped: list[str] = []
    for p in parameters:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


async def _fetch_daily_rows(
    session: AsyncSession,
    *,
    location_id: int,
    parameters: Sequence[str],
    date_from: date,
    date_to: date,
    source: WeatherSource,
) -> list[dict[str, Any]]:
    cols = [
        WeatherDaily.time,
        WeatherDaily.location_id,
        WeatherDaily.source,
        *(getattr(WeatherDaily, p) for p in parameters),
    ]
    stmt = select(*cols).where(
        WeatherDaily.location_id == location_id,
        WeatherDaily.time >= date_from,
        WeatherDaily.time <= date_to,
    )
    if source != "average":
        stmt = stmt.where(WeatherDaily.source == source)
    result = await session.execute(stmt)
    raw: list[dict[str, Any]] = []
    for row in result.all():
        d: dict[str, Any] = {
            "time": row.time,
            "location_id": row.location_id,
            "source": row.source,
        }
        for p in parameters:
            d[p] = getattr(row, p)
        raw.append(d)
    if source == "average":
        return collapse_to_average(raw, parameters)
    return raw


async def get_correlations(
    session: AsyncSession,
    *,
    location_id: int,
    parameters: Sequence[str],
    date_from: date,
    date_to: date,
    source: WeatherSource = "average",
) -> dict[str, Any]:
    """Fetch daily rows for the location and compute Pearson matrix."""
    params = _validate_parameters(parameters)
    if date_from > date_to:
        raise ValueError("date_from must be <= date_to")

    rows = await _fetch_daily_rows(
        session,
        location_id=location_id,
        parameters=params,
        date_from=date_from,
        date_to=date_to,
        source=source,
    )
    return compute_correlations(rows, params)
