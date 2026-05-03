from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Crop


async def list_crops(session: AsyncSession) -> Sequence[Crop]:
    stmt = select(Crop).order_by(Crop.name)
    result = await session.execute(stmt)
    return result.scalars().all()
