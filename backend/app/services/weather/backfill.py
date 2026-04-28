"""History backfill orchestration.

Loads ≥10 years of daily weather for a single location from each source
(Open-Meteo + NASA POWER), chunked one year at a time so we stay well under
upstream rate limits, and writes rows via an idempotent UPSERT.

Progress is persisted on `Location.import_status` / `import_progress` so the
UI / `GET /api/locations/{id}/import-status` endpoint can poll while the
background task is running.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Location
from app.services.weather import ingest, nasa_power, open_meteo
from app.services.weather.dto import WeatherDailyDTO

logger = structlog.get_logger(__name__)

# History depth per PRD §1: "at least 10 years".
DEFAULT_HISTORY_YEARS = 10

# Source -> (callable, label) for chunked historical fetches.
HistoryFetcher = Callable[..., Awaitable[Sequence[WeatherDailyDTO]]]


def _yearly_chunks(date_from: date, date_to: date) -> list[tuple[date, date]]:
    """Split [date_from, date_to] into inclusive 1-calendar-year chunks."""
    chunks: list[tuple[date, date]] = []
    cursor = date_from
    while cursor <= date_to:
        try:
            next_year_start = cursor.replace(year=cursor.year + 1)
        except ValueError:
            # Feb 29 → Feb 28 of next non-leap year.
            next_year_start = cursor.replace(year=cursor.year + 1, day=28)
        chunk_end = min(date_to, date.fromordinal(next_year_start.toordinal() - 1))
        chunks.append((cursor, chunk_end))
        cursor = date.fromordinal(chunk_end.toordinal() + 1)
    return chunks


async def _set_status(
    session: AsyncSession,
    location_id: int,
    *,
    status: str | None = None,
    progress: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    error: str | None = None,
) -> None:
    """Persist a partial update on import tracking columns."""
    loc = await session.get(Location, location_id)
    if loc is None:
        return
    if status is not None:
        loc.import_status = status
    if progress is not None:
        loc.import_progress = max(0, min(100, progress))
    if started_at is not None:
        loc.import_started_at = started_at
    if finished_at is not None:
        loc.import_finished_at = finished_at
    if error is not None:
        loc.import_error = error
    await session.commit()


async def run_backfill(
    session_factory: async_sessionmaker[AsyncSession],
    location_id: int,
    *,
    years: int = DEFAULT_HISTORY_YEARS,
    today: date | None = None,
    fetchers: dict[str, HistoryFetcher] | None = None,
) -> None:
    """Backfill ``years`` of daily history for ``location_id``.

    Idempotent — safe to re-run; existing rows are overwritten via UPSERT.
    All DB updates happen inside short-lived sessions opened from
    ``session_factory`` so the long-running task doesn't hold a single
    connection for the duration.

    Parameters
    ----------
    session_factory:
        ``async_sessionmaker`` to open one session per chunk.
    location_id:
        Target location.
    years:
        How many years to walk back from ``today``.
    today:
        Override end date (used in tests). Defaults to ``date.today()``.
    fetchers:
        Source-name → async callable. Defaults to Open-Meteo + NASA POWER
        historical fetchers. Allows tests to inject in-memory stand-ins.
    """
    today = today or date.today()
    date_from = today.replace(year=today.year - years)
    date_to = today

    if fetchers is None:
        fetchers = {
            "open_meteo": open_meteo.fetch_historical,
            "nasa_power": nasa_power.fetch_historical,
        }

    # Resolve location coords and mark task as started.
    async with session_factory() as session:
        loc = await session.get(Location, location_id)
        if loc is None:
            logger.warning("backfill.location_missing", location_id=location_id)
            return
        lat, lon = loc.latitude, loc.longitude
        await _set_status(
            session,
            location_id,
            status="in_progress",
            progress=0,
            started_at=datetime.now(UTC),
            error="",
        )

    chunks = _yearly_chunks(date_from, date_to)
    total_steps = len(chunks) * len(fetchers)
    completed_steps = 0

    logger.info(
        "backfill.start",
        location_id=location_id,
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        chunks=len(chunks),
        sources=list(fetchers.keys()),
    )

    try:
        for chunk_from, chunk_to in chunks:
            for source, fetcher in fetchers.items():
                try:
                    rows = await fetcher(
                        lat,
                        lon,
                        chunk_from,
                        chunk_to,
                        location_id=location_id,
                    )
                except Exception:
                    logger.exception(
                        "backfill.fetch_failed",
                        location_id=location_id,
                        source=source,
                        chunk_from=chunk_from.isoformat(),
                        chunk_to=chunk_to.isoformat(),
                    )
                    rows = []

                if rows:
                    async with session_factory() as session:
                        await ingest.upsert_weather_daily(session, location_id, rows)

                completed_steps += 1
                progress = int(completed_steps / total_steps * 100) if total_steps else 100
                async with session_factory() as session:
                    await _set_status(session, location_id, progress=progress)

        async with session_factory() as session:
            await _set_status(
                session,
                location_id,
                status="done",
                progress=100,
                finished_at=datetime.now(UTC),
            )
        logger.info("backfill.done", location_id=location_id)
    except Exception as exc:
        logger.exception("backfill.failed", location_id=location_id)
        async with session_factory() as session:
            await _set_status(
                session,
                location_id,
                status="error",
                finished_at=datetime.now(UTC),
                error=str(exc),
            )
        raise
