from typing import Annotated

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.crop import CropResponse
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
