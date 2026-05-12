"""env→DB secret resolver (task 6.3).

`get_secret(name)` returns the effective runtime value for a known secret:

  1. Decrypted DB value when set (DB wins).
  2. Otherwise the corresponding ``os.environ`` value.
  3. Otherwise ``None``.

This single chokepoint replaces direct `os.environ` / `Settings` reads in every
client that needs a rotating secret (OpenWeatherMap, Telegram bot, Yandex.Disk),
so the admin can override env values from the Settings UI without redeploy.
"""

from __future__ import annotations

from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.encryption import decrypt
from app.db.session import async_session_factory
from app.services.settings.store import SECRET_FIELDS, load_raw


class _SecretSpec(NamedTuple):
    group: str
    field: str
    settings_attr: str


_SECRETS: dict[str, _SecretSpec] = {
    "openweathermap_api_key": _SecretSpec(
        group="api_keys",
        field="openweathermap_api_key",
        settings_attr="OPENWEATHERMAP_API_KEY",
    ),
    "telegram_bot_token": _SecretSpec(
        group="telegram",
        field="bot_token",
        settings_attr="TELEGRAM_BOT_TOKEN",
    ),
    "yandex_disk_login": _SecretSpec(
        group="backup",
        field="yandex_disk_login",
        settings_attr="YANDEX_DISK_LOGIN",
    ),
    "yandex_disk_app_password": _SecretSpec(
        group="backup",
        field="yandex_disk_app_password",
        settings_attr="YANDEX_DISK_APP_PASSWORD",
    ),
}


async def _read_field(session: AsyncSession, group: str, field: str) -> str | None:
    raw = await load_raw(session, group)
    val = raw.get(field)
    if val is None or val == "":
        return None
    if field in SECRET_FIELDS.get(group, set()):
        return decrypt(val)
    return val


async def get_secret(
    name: str, session: AsyncSession | None = None
) -> str | None:
    """Return the runtime value for the secret ``name``.

    When ``session`` is omitted, a short-lived session is opened from the
    global ``async_session_factory``. Pass ``session`` explicitly to reuse an
    open transaction (cheaper, avoids nested sessions).

    Raises :class:`ValueError` for unknown secret names — every consumer is
    expected to declare a key in ``_SECRETS`` rather than typo silently.
    """
    if name not in _SECRETS:
        raise ValueError(f"unknown secret: {name!r}")
    spec = _SECRETS[name]

    if session is None:
        async with async_session_factory() as new_session:
            db_value = await _read_field(new_session, spec.group, spec.field)
    else:
        db_value = await _read_field(session, spec.group, spec.field)

    if db_value:
        return db_value

    env_value = getattr(get_settings(), spec.settings_attr, None)
    return env_value or None
