from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.db.models import User
from app.db.session import get_db
from app.schemas.crop import CropCreate, CropResponse, CropUpdate
from app.services import crop as crop_service

router = APIRouter(prefix="/crops", tags=["crops"])
log = structlog.get_logger()


@router.get(
    "",
    response_model=list[CropResponse],
    summary="List crops dictionary (sorted by name)",
)
async def list_crops(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
):
    items = await crop_service.list_crops(session)
    log.info("crops.listed", count=len(items))
    return list(items)


@router.post(
    "",
    response_model=CropResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a crop (admin)",
    description="Admin-only. Returns 409 if a crop with the same name exists.",
)
async def create_crop(
    body: CropCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    return await crop_service.create_crop(session, data=body, actor=admin)


@router.put(
    "/{crop_id}",
    response_model=CropResponse,
    summary="Update a crop (admin)",
    description=(
        "Admin-only. Partial updates allowed — only supplied fields are "
        "changed. Returns 404 if crop is missing, 409 if renaming would "
        "collide with another crop."
    ),
)
async def update_crop(
    crop_id: int,
    body: CropUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
):
    return await crop_service.update_crop(
        session, crop_id=crop_id, data=body, actor=admin
    )


@router.delete(
    "/{crop_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a crop (admin)",
    description=(
        "Admin-only. Returns 409 if the crop is referenced by any "
        "`field_events` or `location_crops`; admin must clean those "
        "up first."
    ),
)
async def delete_crop(
    crop_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> Response:
    await crop_service.delete_crop(session, crop_id=crop_id, actor=admin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
