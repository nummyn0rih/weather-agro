"""Scheduled background jobs.

Each public function:

* opens its own DB sessions from ``async_session_factory`` (do not pass a
  session through APScheduler — jobs run outside the request lifecycle);
* writes a :class:`SchedulerLog` row recording start, finish, duration,
  status, and any error;
* swallows per-location failures so one bad upstream call doesn't kill
  the whole batch — exceptions are logged and counted.

Jobs are registered into an ``AsyncIOScheduler`` by
:func:`app.scheduler.scheduler.register_jobs`.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models import AlertHistory, AlertRule, Location, SchedulerLog
from app.db.session import async_session_factory
from app.services.alerts import engine as alerts_engine
from app.services.alerts.notifier import notify_alert
from app.services.analytics import climate_normals as normals_service
from app.services.backup import runner as backup_runner
from app.services.settings import resolver as settings_resolver
from app.services.weather import ingest, nasa_power, open_meteo

logger = structlog.get_logger(__name__)

DAILY_INGEST_JOB_ID = "daily_ingest"
FORECAST_REFRESH_JOB_ID = "forecast_refresh"
CLIMATE_NORMALS_JOB_ID = "climate_normals_recompute"
EVALUATE_ALERTS_JOB_ID = "evaluate_alerts"
BACKUP_JOB_ID = "backup_to_yandex_disk"


async def _list_locations(session: AsyncSession) -> list[Location]:
    result = await session.execute(select(Location))
    return list(result.scalars().all())


async def _record_log(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    job_id: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    duration_ms: int,
    items_processed: int,
    error: str | None,
) -> None:
    async with session_factory() as session:
        session.add(
            SchedulerLog(
                job_id=job_id,
                started_at=started_at,
                finished_at=finished_at,
                status=status,
                duration_ms=duration_ms,
                items_processed=items_processed,
                error=error,
            )
        )
        await session.commit()


async def _run_with_log(
    job_id: str,
    work: Callable[[async_sessionmaker[AsyncSession]], Awaitable[int]],
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Run ``work`` and persist a SchedulerLog row regardless of outcome."""
    factory = session_factory or async_session_factory
    started_at = datetime.now(UTC)
    t0 = time.monotonic()
    items = 0
    status = "success"
    error: str | None = None

    try:
        items = await work(factory)
    except Exception as exc:
        status = "error"
        error = f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()}"
        logger.exception("scheduler.job_failed", job_id=job_id)

    finished_at = datetime.now(UTC)
    duration_ms = int((time.monotonic() - t0) * 1000)

    try:
        await _record_log(
            factory,
            job_id=job_id,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            duration_ms=duration_ms,
            items_processed=items,
            error=error,
        )
    except Exception:
        logger.exception("scheduler.log_write_failed", job_id=job_id)

    logger.info(
        "scheduler.job_done",
        job_id=job_id,
        status=status,
        duration_ms=duration_ms,
        items=items,
    )


async def _ingest_yesterday(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    target_day: date | None = None,
) -> int:
    """Fetch yesterday's daily weather from all sources for every location.

    Returns the number of (location, source) batches successfully written.
    """
    target = target_day or (datetime.now(UTC).date() - timedelta(days=1))

    async with session_factory() as session:
        locations = await _list_locations(session)

    sources: dict[str, Callable[..., Awaitable[Any]]] = {
        "open_meteo": open_meteo.fetch_historical,
        "nasa_power": nasa_power.fetch_historical,
    }

    written = 0
    for loc in locations:
        for source, fetcher in sources.items():
            try:
                rows = await fetcher(
                    loc.latitude,
                    loc.longitude,
                    target,
                    target,
                    location_id=loc.id,
                )
            except Exception:
                logger.exception(
                    "scheduler.daily_ingest.fetch_failed",
                    location_id=loc.id,
                    source=source,
                    target=target.isoformat(),
                )
                continue

            if not rows:
                continue

            try:
                async with session_factory() as session:
                    await ingest.upsert_weather_daily(session, loc.id, rows)
                written += 1
            except Exception:
                logger.exception(
                    "scheduler.daily_ingest.upsert_failed",
                    location_id=loc.id,
                    source=source,
                )

    return written


async def _refresh_forecast(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    days: int = 16,
) -> int:
    """Refresh ``days``-day forecast for every location (Open-Meteo only)."""
    async with session_factory() as session:
        locations = await _list_locations(session)

    written = 0
    for loc in locations:
        try:
            rows = await open_meteo.fetch_forecast(
                loc.latitude,
                loc.longitude,
                days=days,
                location_id=loc.id,
            )
        except Exception:
            logger.exception(
                "scheduler.forecast_refresh.fetch_failed",
                location_id=loc.id,
            )
            continue

        if not rows:
            continue

        try:
            async with session_factory() as session:
                await ingest.upsert_weather_forecast(session, loc.id, rows)
            written += 1
        except Exception:
            logger.exception(
                "scheduler.forecast_refresh.upsert_failed",
                location_id=loc.id,
            )

    return written


async def daily_ingest_job(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Entry point for the 03:00 MSK daily ingest job."""
    await _run_with_log(
        DAILY_INGEST_JOB_ID,
        _ingest_yesterday,
        session_factory=session_factory,
    )


async def forecast_refresh_job(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Entry point for the 06:00 / 18:00 MSK forecast refresh job."""
    await _run_with_log(
        FORECAST_REFRESH_JOB_ID,
        _refresh_forecast,
        session_factory=session_factory,
    )


async def _recompute_climate_normals(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Recompute climate normals for every location. Returns rows written."""
    async with session_factory() as session:
        return await normals_service.recompute_all(session)


async def climate_normals_job(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Entry point for the 1st-of-month climate normals recompute job."""
    await _run_with_log(
        CLIMATE_NORMALS_JOB_ID,
        _recompute_climate_normals,
        session_factory=session_factory,
    )


async def _evaluate_alerts(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Evaluate every enabled alert rule. Returns triggers recorded.

    When ``TELEGRAM_BOT_TOKEN`` is configured, fired alerts are pushed to
    every Telegram chat bound to a user. The notifier opens a dedicated
    DB session per dispatch to avoid sharing connections with the
    evaluator's transaction.
    """
    settings = get_settings()
    dedup_hours = settings.ALERTS_DEDUP_HOURS
    token = await settings_resolver.get_secret("telegram_bot_token")

    if not token:
        async with session_factory() as session:
            return await alerts_engine.evaluate_all(
                session, dedup_hours=dedup_hours
            )

    async with httpx.AsyncClient() as client:
        async def notifier(rule: AlertRule, history: AlertHistory) -> None:
            async with session_factory() as notify_session:
                await notify_alert(
                    notify_session, client, token, rule, history
                )

        async with session_factory() as session:
            return await alerts_engine.evaluate_all(
                session, dedup_hours=dedup_hours, notifier=notifier
            )


async def evaluate_alerts_job(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Entry point for the hourly alert evaluation job."""
    await _run_with_log(
        EVALUATE_ALERTS_JOB_ID,
        _evaluate_alerts,
        session_factory=session_factory,
    )


async def _run_backup(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Execute one scheduled backup. Returns 1 on success, 0 on error.

    Persistence of ``BackupLog`` is handled inside
    :func:`app.services.backup.runner.run_backup`; the ``SchedulerLog`` row
    written by ``_run_with_log`` is the cross-job audit trail.
    """
    result = await backup_runner.run_backup(
        kind="scheduled", session_factory=session_factory
    )
    if result.status != "success":
        # Propagate so the SchedulerLog row records 'error'.
        raise RuntimeError(result.error or "backup failed")
    return 1


async def backup_job(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Entry point for the 04:00 MSK Yandex.Disk backup job (task 6.2)."""
    await _run_with_log(
        BACKUP_JOB_ID,
        _run_backup,
        session_factory=session_factory,
    )
