from datetime import date
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import FieldEvent
from app.schemas.field_event import FieldEventCreate, FieldEventUpdate
from app.schemas.weather import ALLOWED_PARAMETERS
from app.services.weather.query import query_daily

_WEATHER_META_KEYS = {"time", "location_id", "source"}


async def list_events(
    session: AsyncSession,
    location_id: int | None = None,
    event_type: str | None = None,
    crop_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Sequence[FieldEvent]:
    stmt = select(FieldEvent)
    if location_id is not None:
        stmt = stmt.where(FieldEvent.location_id == location_id)
    if event_type is not None:
        stmt = stmt.where(FieldEvent.event_type == event_type)
    if crop_id is not None:
        stmt = stmt.where(FieldEvent.crop_id == crop_id)
    if date_from is not None:
        stmt = stmt.where(FieldEvent.event_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(FieldEvent.event_date <= date_to)
    stmt = stmt.order_by(FieldEvent.event_date.desc(), FieldEvent.id.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_event(session: AsyncSession, event_id: int) -> FieldEvent | None:
    result = await session.execute(
        select(FieldEvent).where(FieldEvent.id == event_id)
    )
    return result.scalar_one_or_none()


async def create_event(
    session: AsyncSession, data: FieldEventCreate
) -> FieldEvent:
    obj = FieldEvent(**data.model_dump(), photos=[])
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update_event(
    session: AsyncSession, event_id: int, data: FieldEventUpdate
) -> FieldEvent | None:
    obj = await get_event(session, event_id)
    if not obj:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_event(session: AsyncSession, event_id: int) -> FieldEvent | None:
    obj = await get_event(session, event_id)
    if not obj:
        return None
    await session.delete(obj)
    await session.commit()
    return obj


async def add_photos(
    session: AsyncSession, event: FieldEvent, urls: list[str]
) -> FieldEvent:
    event.photos = list(event.photos) + urls
    flag_modified(event, "photos")
    await session.commit()
    await session.refresh(event)
    return event


async def remove_photo(
    session: AsyncSession, event: FieldEvent, url: str
) -> FieldEvent:
    event.photos = [p for p in event.photos if p != url]
    flag_modified(event, "photos")
    await session.commit()
    await session.refresh(event)
    return event


async def get_event_weather(
    session: AsyncSession, location_id: int, event_date: date
) -> dict[str, Any] | None:
    """Cross-source averaged weather for the event's location and date.

    Returns ``None`` if no source has data for that day.
    """
    rows = await query_daily(
        session,
        location_ids=[location_id],
        parameters=sorted(ALLOWED_PARAMETERS),
        date_from=event_date,
        date_to=event_date,
        source="average",
        aggregation="day",
    )
    if not rows:
        return None
    row = rows[0]
    return {k: v for k, v in row.items() if k not in _WEATHER_META_KEYS}
