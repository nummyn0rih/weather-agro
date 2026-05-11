from collections.abc import Sequence

import structlog
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Crop, FieldEvent, LocationCrop, User
from app.schemas.crop import CropCreate, CropUpdate

log = structlog.get_logger()


async def list_crops(session: AsyncSession) -> Sequence[Crop]:
    stmt = select(Crop).order_by(Crop.name)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_crop(session: AsyncSession, crop_id: int) -> Crop:
    crop = await session.get(Crop, crop_id)
    if crop is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Crop not found")
    return crop


async def _name_exists(
    session: AsyncSession, name: str, *, exclude_id: int | None = None
) -> bool:
    stmt = select(Crop.id).where(Crop.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Crop.id != exclude_id)
    return (await session.execute(stmt)).scalar_one_or_none() is not None


async def create_crop(
    session: AsyncSession, *, data: CropCreate, actor: User
) -> Crop:
    if await _name_exists(session, data.name):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Crop with this name already exists"
        )
    crop = Crop(
        name=data.name,
        base_temperature=data.base_temperature,
        optimal_temp_min=data.optimal_temp_min,
        optimal_temp_max=data.optimal_temp_max,
    )
    session.add(crop)
    await session.commit()
    await session.refresh(crop)
    log.info(
        "admin.crop_created",
        crop_id=crop.id,
        name=crop.name,
        actor=actor.username,
    )
    return crop


async def update_crop(
    session: AsyncSession, *, crop_id: int, data: CropUpdate, actor: User
) -> Crop:
    crop = await get_crop(session, crop_id)
    payload = data.model_dump(exclude_unset=True)

    if "name" in payload and payload["name"] != crop.name:
        if await _name_exists(session, payload["name"], exclude_id=crop_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Crop with this name already exists"
            )

    changed: dict[str, object] = {}
    for field, value in payload.items():
        if getattr(crop, field) != value:
            setattr(crop, field, value)
            changed[field] = value

    if changed:
        await session.commit()
        await session.refresh(crop)
        log.info(
            "admin.crop_updated",
            crop_id=crop.id,
            fields=list(changed.keys()),
            actor=actor.username,
        )
    return crop


async def _count_references(
    session: AsyncSession, crop_id: int
) -> tuple[int, int]:
    fe_count = (
        await session.execute(
            select(func.count(FieldEvent.id)).where(FieldEvent.crop_id == crop_id)
        )
    ).scalar_one()
    lc_count = (
        await session.execute(
            select(func.count())
            .select_from(LocationCrop)
            .where(LocationCrop.crop_id == crop_id)
        )
    ).scalar_one()
    return int(fe_count), int(lc_count)


async def delete_crop(
    session: AsyncSession, *, crop_id: int, actor: User
) -> None:
    crop = await get_crop(session, crop_id)
    fe_count, lc_count = await _count_references(session, crop_id)
    if fe_count or lc_count:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"Crop is referenced by {fe_count} field_events "
                    f"/ {lc_count} location_crops"
                ),
                "references": {
                    "field_events": fe_count,
                    "location_crops": lc_count,
                },
            },
        )
    name = crop.name
    await session.delete(crop)
    await session.commit()
    log.info(
        "admin.crop_deleted",
        crop_id=crop_id,
        name=name,
        actor=actor.username,
    )
