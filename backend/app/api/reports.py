from pathlib import Path
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.models import Location, User
from app.db.session import async_session_factory, get_db
from app.schemas.report import ReportGenerateRequest, ReportResponse
from app.services.reports import service as report_service

router = APIRouter(prefix="/reports", tags=["reports"])
log = structlog.get_logger()


@router.post(
    "/generate",
    response_model=ReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Schedule generation of a season PDF report (returns file_id immediately)",
)
async def generate_report(
    body: ReportGenerateRequest,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ReportResponse:
    location = await session.get(Location, body.location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")

    obj = await report_service.create_pending_report(
        session, location_id=body.location_id, season_year=body.season_year
    )
    settings = get_settings()
    background_tasks.add_task(
        report_service.run_generation,
        async_session_factory,
        report_id=obj.id,
        upload_dir=settings.UPLOAD_DIR,
    )
    log.info(
        "report.generate.scheduled",
        report_id=obj.id,
        location_id=body.location_id,
        season_year=body.season_year,
    )
    return ReportResponse.model_validate(obj)


@router.get(
    "",
    response_model=list[ReportResponse],
    summary="List reports (optionally filtered by location)",
)
async def list_reports(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> list[ReportResponse]:
    from app.db.models import Report

    result = await session.execute(select(Report).order_by(Report.created_at.desc()))
    return [ReportResponse.model_validate(r) for r in result.scalars().all()]


@router.get(
    "/{file_id}",
    response_model=ReportResponse,
    summary="Get report metadata by id",
)
async def get_report_meta(
    file_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> ReportResponse:
    obj = await report_service.get_report(session, file_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    return ReportResponse.model_validate(obj)


@router.get(
    "/{file_id}/download",
    summary="Download generated PDF report",
    response_class=FileResponse,
)
async def download_report(
    file_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> FileResponse:
    obj = await report_service.get_report(session, file_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Report not found")
    if obj.status != "done" or not obj.file_path:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Report not ready (status={obj.status})",
        )
    path = Path(obj.file_path)
    if not path.exists():
        log.error("report.download.missing_file", report_id=file_id, path=str(path))
        raise HTTPException(
            status.HTTP_410_GONE, "Report file is missing on disk"
        )
    log.info("report.downloaded", report_id=file_id, bytes=obj.file_size_bytes)
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        filename=f"report_{file_id}.pdf",
    )
