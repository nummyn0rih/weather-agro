"""Persistence layer for weather DTOs.

Writes `WeatherDailyDTO` rows into `weather_daily` / `weather_forecast` tables
using PostgreSQL `INSERT … ON CONFLICT` so retries are idempotent: re-running
an ingest for the same `(time, location_id, source)` overwrites the previous
row instead of duplicating it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WeatherDaily, WeatherForecast
from app.services.weather.dto import WeatherDailyDTO

logger = structlog.get_logger(__name__)

_PK_COLUMNS = ("time", "location_id", "source")


def _to_row(dto: WeatherDailyDTO, location_id: int) -> dict:
    row = asdict(dto)
    row["location_id"] = location_id
    return row


async def upsert_weather_daily(
    session: AsyncSession,
    location_id: int,
    rows: Sequence[WeatherDailyDTO],
) -> int:
    """Idempotent batch insert into `weather_daily`. Returns row count written."""
    if not rows:
        return 0

    payload = [_to_row(r, location_id) for r in rows]
    stmt = pg_insert(WeatherDaily).values(payload)
    update_cols = {
        col.name: stmt.excluded[col.name]
        for col in WeatherDaily.__table__.columns
        if col.name not in _PK_COLUMNS
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=list(_PK_COLUMNS),
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.commit()
    logger.info(
        "weather_daily.upsert",
        location_id=location_id,
        rows=len(payload),
    )
    return len(payload)


async def upsert_weather_forecast(
    session: AsyncSession,
    location_id: int,
    rows: Sequence[WeatherDailyDTO],
) -> int:
    """Idempotent batch insert into `weather_forecast`. Returns row count written."""
    if not rows:
        return 0

    payload = [_to_row(r, location_id) for r in rows]
    stmt = pg_insert(WeatherForecast).values(payload)
    update_cols = {
        col.name: stmt.excluded[col.name]
        for col in WeatherForecast.__table__.columns
        if col.name not in _PK_COLUMNS
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=list(_PK_COLUMNS),
        set_=update_cols,
    )
    await session.execute(stmt)
    await session.commit()
    logger.info(
        "weather_forecast.upsert",
        location_id=location_id,
        rows=len(payload),
    )
    return len(payload)
