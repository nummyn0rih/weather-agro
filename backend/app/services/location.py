from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Location
from app.schemas.location import LocationCreate, LocationUpdate


async def list_locations(
    session: AsyncSession,
    region: str | None = None,
    type_: str | None = None,
) -> Sequence[Location]:
    stmt = select(Location)
    if region:
        stmt = stmt.where(Location.region == region)
    if type_:
        stmt = stmt.where(Location.type == type_)
    stmt = stmt.order_by(Location.id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_location(session: AsyncSession, location_id: int) -> Location | None:
    result = await session.execute(select(Location).where(Location.id == location_id))
    return result.scalar_one_or_none()


async def create_location(session: AsyncSession, data: LocationCreate) -> Location:
    obj = Location(**data.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update_location(
    session: AsyncSession, location_id: int, data: LocationUpdate
) -> Location | None:
    obj = await get_location(session, location_id)
    if not obj:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_location(session: AsyncSession, location_id: int) -> bool:
    obj = await get_location(session, location_id)
    if not obj:
        return False
    await session.delete(obj)
    await session.commit()
    return True
