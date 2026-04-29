"""AsyncIOScheduler factory + job registration.

Schedules (Moscow time, Europe/Moscow):

* 03:00 — daily ingest of yesterday's weather (all sources, all locations)
* 06:00 — forecast refresh
* 18:00 — forecast refresh

Misfires (e.g. app down at trigger time) are coalesced and given a 1h
``misfire_grace_time`` so a delayed start still runs the job once.
"""

from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.scheduler.jobs import (
    CLIMATE_NORMALS_JOB_ID,
    DAILY_INGEST_JOB_ID,
    FORECAST_REFRESH_JOB_ID,
    climate_normals_job,
    daily_ingest_job,
    forecast_refresh_job,
)

logger = structlog.get_logger(__name__)

SCHEDULER_TZ = "Europe/Moscow"


def register_jobs(scheduler: AsyncIOScheduler) -> None:
    """Attach default jobs to ``scheduler``. Idempotent: replaces existing IDs."""
    scheduler.add_job(
        daily_ingest_job,
        trigger=CronTrigger(hour=3, minute=0, timezone=SCHEDULER_TZ),
        id=DAILY_INGEST_JOB_ID,
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        forecast_refresh_job,
        trigger=CronTrigger(hour="6,18", minute=0, timezone=SCHEDULER_TZ),
        id=FORECAST_REFRESH_JOB_ID,
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        climate_normals_job,
        trigger=CronTrigger(day=1, hour=2, minute=0, timezone=SCHEDULER_TZ),
        id=CLIMATE_NORMALS_JOB_ID,
        replace_existing=True,
        coalesce=True,
        misfire_grace_time=3600,
    )
    logger.info(
        "scheduler.jobs_registered",
        jobs=[
            DAILY_INGEST_JOB_ID,
            FORECAST_REFRESH_JOB_ID,
            CLIMATE_NORMALS_JOB_ID,
        ],
        timezone=SCHEDULER_TZ,
    )


def create_scheduler() -> AsyncIOScheduler:
    """Build a fresh AsyncIOScheduler with all default jobs attached."""
    scheduler = AsyncIOScheduler(timezone=SCHEDULER_TZ)
    register_jobs(scheduler)
    return scheduler
