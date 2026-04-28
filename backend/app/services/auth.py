from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Lookup user by username. Single source of truth for tests to monkeypatch."""
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()
