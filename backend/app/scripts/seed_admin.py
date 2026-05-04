"""Seed admin user from ADMIN_USERNAME / ADMIN_PASSWORD.

Idempotent:
- Creates user with `is_admin=true`, `is_active=true` if missing.
- If user exists — repairs the flags (sets `is_admin=true`, `is_active=true`)
  but does NOT reset the password. Operator must drop the user manually
  before re-seeding to rotate the password.

Run: docker compose exec backend python -m app.scripts.seed_admin
"""

import asyncio

import structlog
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.models import User
from app.db.session import async_session_factory, engine


async def seed_admin() -> None:
    log = structlog.get_logger()
    settings = get_settings()
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        log.warning(
            "auth.seed_admin_skipped", reason="ADMIN_USERNAME/PASSWORD not set"
        )
        return

    async with async_session_factory() as session:
        existing = await session.execute(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        user = existing.scalar_one_or_none()

        if user is None:
            session.add(
                User(
                    username=settings.ADMIN_USERNAME,
                    password_hash=hash_password(settings.ADMIN_PASSWORD),
                    is_admin=True,
                    is_active=True,
                )
            )
            await session.commit()
            log.info("auth.admin_created", username=settings.ADMIN_USERNAME)
            return

        repaired = False
        if not user.is_admin:
            user.is_admin = True
            repaired = True
        if not user.is_active:
            user.is_active = True
            repaired = True
        if repaired:
            await session.commit()
            log.info("auth.admin_flags_repaired", username=settings.ADMIN_USERNAME)
        else:
            log.info("auth.admin_already_seeded", username=settings.ADMIN_USERNAME)


async def _main() -> None:
    configure_logging()
    try:
        await seed_admin()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
