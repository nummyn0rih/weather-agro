"""DB-side helpers for the reports module (CRUD + background generation runner)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Location, Report
from app.services.reports import pdf_generator

log = structlog.get_logger()


def report_file_path(upload_dir: str, report_id: int) -> Path:
    return Path(upload_dir) / "reports" / f"{report_id}.pdf"


async def create_pending_report(
    session: AsyncSession, *, location_id: int, season_year: int
) -> Report:
    obj = Report(
        location_id=location_id,
        season_year=season_year,
        status="pending",
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_report(session: AsyncSession, report_id: int) -> Report | None:
    result = await session.execute(select(Report).where(Report.id == report_id))
    return result.scalar_one_or_none()


async def delete_report(session: AsyncSession, report_id: int) -> bool:
    """Delete report row and its PDF file from disk.

    Returns ``True`` if the row existed (and was deleted), ``False`` otherwise.
    Missing file on disk is not an error — the DB row is removed regardless and
    a warning is logged.
    """
    obj = await get_report(session, report_id)
    if obj is None:
        return False

    file_path = obj.file_path
    await session.delete(obj)
    await session.commit()

    if file_path:
        path = Path(file_path)
        try:
            path.unlink()
        except FileNotFoundError:
            log.warning("report.delete.file_missing", report_id=report_id, path=str(path))
        except OSError as exc:
            log.error(
                "report.delete.file_unlink_failed",
                report_id=report_id,
                path=str(path),
                error=str(exc),
            )
    return True


async def run_generation(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    report_id: int,
    upload_dir: str,
) -> None:
    """Background-task entry point: load location, render PDF, persist status.

    Wraps everything in a try/except so a failure in generation doesn't kill the
    background task silently — instead we mark the report row as ``error``.
    """
    output_path = report_file_path(upload_dir, report_id)

    async with session_factory() as session:
        report = await get_report(session, report_id)
        if report is None:
            log.error("report.run.missing", report_id=report_id)
            return
        if report.location_id is None:
            report.status = "error"
            report.error = "Location was deleted"
            report.finished_at = datetime.now(timezone.utc)
            await session.commit()
            log.warning("report.run.no_location", report_id=report_id)
            return

        location = await session.get(Location, report.location_id)
        if location is None:
            report.status = "error"
            report.error = "Location not found"
            report.finished_at = datetime.now(timezone.utc)
            await session.commit()
            log.warning("report.run.location_missing", report_id=report_id)
            return

        report.status = "in_progress"
        await session.commit()
        log.info(
            "report.run.start",
            report_id=report_id,
            location_id=location.id,
            season_year=report.season_year,
        )

        try:
            size = await pdf_generator.generate_season_report(
                session,
                location=location,
                season_year=report.season_year,
                output_path=output_path,
            )
        except Exception as exc:
            log.exception(
                "report.run.failed",
                report_id=report_id,
                error=str(exc),
            )
            report.status = "error"
            report.error = str(exc)[:500]
            report.finished_at = datetime.now(timezone.utc)
            await session.commit()
            return

        report.status = "done"
        report.file_path = str(output_path)
        report.file_size_bytes = size
        report.finished_at = datetime.now(timezone.utc)
        await session.commit()
        log.info("report.run.done", report_id=report_id, bytes=size)
