"""Low-level read/write helpers for the `settings` JSONB table (task 6.3).

One row per group (key ∈ {sources, api_keys, telegram, backup}). Values are
stored as JSONB dicts. Field-level encryption/masking is the caller's
responsibility — this module is intentionally schema-agnostic.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Setting

# Per-group set of field names that hold encrypted (Fernet) values.
SECRET_FIELDS: dict[str, set[str]] = {
    "api_keys": {"openweathermap_api_key"},
    "telegram": {"bot_token"},
    "backup": {"yandex_disk_app_password"},
    "sources": set(),
}


async def load_raw(session: AsyncSession, key: str) -> dict[str, Any]:
    """Return the JSONB value for ``key`` as a plain dict, or `{}` when absent.

    Returned dict is a shallow copy — safe to mutate without affecting the
    ORM-tracked attribute.
    """
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        return {}
    value = row.value or {}
    return dict(value)


async def save_raw(session: AsyncSession, key: str, value: dict[str, Any]) -> None:
    """Upsert the JSONB value for ``key``. Caller is responsible for commit."""
    result = await session.execute(select(Setting).where(Setting.key == key))
    row = result.scalar_one_or_none()
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.flush()
