from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.models import Location, User
from app.db.session import async_session_factory, get_db
from app.schemas.location import (
    LocationCreate,
    LocationImportStatus,
    LocationResponse,
    LocationType,
    LocationUpdate,
)
from app.services import location as location_service
from app.services.weather import backfill as backfill_service

router = APIRouter(prefix="/locations", tags=["locations"])
log = structlog.get_logger()


@router.get(
    "",
    response_model=list[LocationResponse],
    summary="List locations (filterable)",
)
async def list_locations(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    region: Annotated[str | None, Query(max_length=100)] = None,
    type: Annotated[LocationType | None, Query()] = None,
) -> list[Location]:
    items = await location_service.list_locations(session, region=region, type_=type)
    return list(items)


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create location (kicks off 10y history backfill)",
)
async def create_location(
    body: LocationCreate,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Location:
    obj = await location_service.create_location(session, body)
    log.info("location.created", id=obj.id, name=obj.name)
    background_tasks.add_task(
        backfill_service.run_backfill,
        async_session_factory,
        obj.id,
    )
    return obj


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Get location by ID",
)
async def get_location(
    location_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> Location:
    obj = await location_service.get_location(session, location_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    return obj


@router.get(
    "/{location_id}/import-status",
    response_model=LocationImportStatus,
    summary="History backfill progress for a location",
)
async def get_import_status(
    location_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> LocationImportStatus:
    snapshot = await location_service.get_import_status(session, location_id)
    if snapshot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    return snapshot


@router.put(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Partial update of location",
)
async def update_location(
    location_id: int,
    body: LocationUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Location:
    obj = await location_service.update_location(session, location_id, body)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    log.info("location.updated", id=location_id)
    return obj


@router.delete(
    "/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete location",
)
async def delete_location(
    location_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> None:
    deleted = await location_service.delete_location(session, location_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Location not found")
    log.info("location.deleted", id=location_id)
