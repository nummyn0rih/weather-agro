"""APScheduler integration: background jobs running on a fixed schedule.

Public surface:
    create_scheduler — build an AsyncIOScheduler with all jobs registered.
    register_jobs    — attach jobs to an existing scheduler.

Job entry points live in :mod:`app.scheduler.jobs`.
"""

from app.scheduler.scheduler import create_scheduler, register_jobs

__all__ = ["create_scheduler", "register_jobs"]
