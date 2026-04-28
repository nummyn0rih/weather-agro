"""Seed admin user from ADMIN_USERNAME / ADMIN_PASSWORD.

Idempotent — `ON CONFLICT DO NOTHING` on `username`. Operator must drop the
user manually before re-seeding to rotate the password.

Run: docker compose exec backend python -m app.scripts.seed_admin
"""

import asyncio

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.models import User
from app.db.session import async_session_factory, engine


async def seed_admin() -> None:
    log = structlog.get_logger()
    settings = get_settings()
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        log.warning("auth.seed_admin_skipped", reason="ADMIN_USERNAME/PASSWORD not set")
        return

    async with async_session_factory() as session:
        stmt = pg_insert(User).values(
            username=settings.ADMIN_USERNAME,
            password_hash=hash_password(settings.ADMIN_PASSWORD),
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["username"])
        await session.execute(stmt)
        await session.commit()

    log.info("auth.admin_seeded", username=settings.ADMIN_USERNAME)


async def _main() -> None:
    configure_logging()
    try:
        await seed_admin()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
