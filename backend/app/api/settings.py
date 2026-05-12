"""Settings API (task 6.3).

Four grouped endpoint pairs — `/sources`, `/api-keys`, `/telegram`, `/backup` —
backed by a single `settings` table row per group. Secrets are encrypted at
rest (Fernet, key derived from `SECRET_KEY` via HKDF) and masked on GET as
``"***" + last4``. PUT semantics for secrets: missing/None → no change;
value starts with ``"***"`` → no change (idempotent re-submit of GET payload);
``""`` → clear; otherwise encrypt + store.

Every PUT emits a structlog `settings.updated` event with the list of changed
field names — secret values are never logged. ADR-002 captures the design.
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.encryption import encrypt
from app.db.models import User
from app.db.session import get_db
from app.schemas.settings import (
    ApiKeysRead,
    ApiKeysUpdate,
    BackupRead,
    BackupUpdate,
    SourcesSettings,
    SourcesUpdate,
    TelegramRead,
    TelegramUpdate,
)
from app.services.settings import resolver
from app.services.settings.store import load_raw, save_raw

router = APIRouter(prefix="/settings", tags=["settings"])
log = structlog.get_logger()

MASK_PREFIX = "***"


def _mask(plain: str | None) -> str | None:
    """Return ``"***" + last4`` (or full mask when shorter than 4)."""
    if not plain:
        return None
    tail = plain[-4:] if len(plain) >= 4 else plain
    return f"{MASK_PREFIX}{tail}"


async def _effective_value(
    session: AsyncSession, name: str
) -> str | None:
    """Return the decrypted, env→DB-resolved value for a known secret/field."""
    return await resolver.get_secret(name, session=session)


def _apply_secret_field(
    *,
    incoming: str | None,
    current_encrypted: Any,
) -> tuple[bool, Any]:
    """Return ``(changed, new_value)`` for a secret field per sentinel rules.

    new_value semantics: when ``changed`` is False the second element is
    unused (caller keeps current). When True, ``None`` means "remove field
    from JSONB" (clear), otherwise it's the new Fernet token.
    """
    if incoming is None:
        return False, None
    if incoming.startswith(MASK_PREFIX):
        return False, None
    if incoming == "":
        if current_encrypted is None:
            return False, None
        return True, None
    return True, encrypt(incoming)


# ── /sources ─────────────────────────────────────────────────────────────────


@router.get(
    "/sources",
    response_model=SourcesSettings,
    summary="Get weather-source priority + average-mode flag",
)
async def get_sources(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SourcesSettings:
    raw = await load_raw(session, "sources")
    return SourcesSettings.model_validate({**SourcesSettings().model_dump(), **raw})


@router.put(
    "/sources",
    response_model=SourcesSettings,
    summary="Update weather-source settings",
    description=(
        "Partial update — fields not supplied (or `null`) are kept. "
        "Returns the merged effective configuration."
    ),
)
async def put_sources(
    body: SourcesUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> SourcesSettings:
    raw = await load_raw(session, "sources")
    base = {**SourcesSettings().model_dump(), **raw}
    updates = body.model_dump(exclude_none=True)
    changed: list[str] = []
    for field, value in updates.items():
        if base.get(field) != value:
            changed.append(field)
        base[field] = value

    validated = SourcesSettings.model_validate(base)
    new_value = validated.model_dump()
    await save_raw(session, "sources", new_value)
    await session.commit()

    log.info(
        "settings.updated",
        group="sources",
        user_id=admin.id,
        changed_keys=changed,
    )
    return validated


# ── /api-keys ────────────────────────────────────────────────────────────────


@router.get(
    "/api-keys",
    response_model=ApiKeysRead,
    summary="Get third-party API keys (masked)",
)
async def get_api_keys(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> ApiKeysRead:
    plain = await _effective_value(session, "openweathermap_api_key")
    return ApiKeysRead(openweathermap_api_key=_mask(plain))


@router.put(
    "/api-keys",
    response_model=ApiKeysRead,
    summary="Update third-party API keys",
    description=(
        "Sentinel PUT: `null`/absent or value starting with `***` keeps the "
        "current secret; empty string clears the DB row (env fallback "
        "resumes); any other value is encrypted and stored."
    ),
)
async def put_api_keys(
    body: ApiKeysUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> ApiKeysRead:
    raw = await load_raw(session, "api_keys")
    changed: list[str] = []

    changed_flag, new_val = _apply_secret_field(
        incoming=body.openweathermap_api_key,
        current_encrypted=raw.get("openweathermap_api_key"),
    )
    if changed_flag:
        if new_val is None:
            raw.pop("openweathermap_api_key", None)
        else:
            raw["openweathermap_api_key"] = new_val
        changed.append("openweathermap_api_key")

    await save_raw(session, "api_keys", raw)
    await session.commit()

    log.info(
        "settings.updated",
        group="api_keys",
        user_id=admin.id,
        changed_keys=changed,
    )
    return await get_api_keys(session, admin)


# ── /telegram ────────────────────────────────────────────────────────────────


@router.get(
    "/telegram",
    response_model=TelegramRead,
    summary="Get Telegram bot token (masked)",
)
async def get_telegram(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> TelegramRead:
    plain = await _effective_value(session, "telegram_bot_token")
    return TelegramRead(bot_token=_mask(plain))


@router.put(
    "/telegram",
    response_model=TelegramRead,
    summary="Update Telegram bot token",
)
async def put_telegram(
    body: TelegramUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> TelegramRead:
    raw = await load_raw(session, "telegram")
    changed: list[str] = []

    changed_flag, new_val = _apply_secret_field(
        incoming=body.bot_token,
        current_encrypted=raw.get("bot_token"),
    )
    if changed_flag:
        if new_val is None:
            raw.pop("bot_token", None)
        else:
            raw["bot_token"] = new_val
        changed.append("bot_token")

    await save_raw(session, "telegram", raw)
    await session.commit()

    log.info(
        "settings.updated",
        group="telegram",
        user_id=admin.id,
        changed_keys=changed,
    )
    return await get_telegram(session, admin)


# ── /backup ─────────────────────────────────────────────────────────────────


@router.get(
    "/backup",
    response_model=BackupRead,
    summary="Get Yandex.Disk backup settings (password masked)",
)
async def get_backup(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> BackupRead:
    raw = await load_raw(session, "backup")
    defaults = BackupRead().model_dump()
    cfg = get_settings()

    login = await _effective_value(session, "yandex_disk_login")
    password_plain = await _effective_value(session, "yandex_disk_app_password")
    path = (
        raw.get("yandex_disk_path")
        or cfg.YANDEX_DISK_BACKUP_PATH
        or defaults["yandex_disk_path"]
    )
    retention_daily = (
        raw.get("retention_daily")
        if raw.get("retention_daily") is not None
        else cfg.BACKUP_RETENTION_DAILY
    )
    retention_monthly = (
        raw.get("retention_monthly")
        if raw.get("retention_monthly") is not None
        else cfg.BACKUP_RETENTION_MONTHLY
    )

    return BackupRead(
        yandex_disk_login=login,
        yandex_disk_app_password=_mask(password_plain),
        yandex_disk_path=path,
        retention_daily=retention_daily,
        retention_monthly=retention_monthly,
    )


@router.put(
    "/backup",
    response_model=BackupRead,
    summary="Update Yandex.Disk backup settings",
    description=(
        "Sentinel PUT — secret fields follow the mask/clear convention; "
        "plain string fields with empty `\"\"` clear the DB override and "
        "fall back to env/defaults."
    ),
)
async def put_backup(
    body: BackupUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> BackupRead:
    raw = await load_raw(session, "backup")
    changed: list[str] = []

    # Login: not encrypted, but follows the same "" = clear / None = keep rule.
    if body.yandex_disk_login is not None:
        if body.yandex_disk_login == "":
            if raw.pop("yandex_disk_login", None) is not None:
                changed.append("yandex_disk_login")
        else:
            if raw.get("yandex_disk_login") != body.yandex_disk_login:
                raw["yandex_disk_login"] = body.yandex_disk_login
                changed.append("yandex_disk_login")

    # App password: secret + sentinel.
    pw_changed, pw_val = _apply_secret_field(
        incoming=body.yandex_disk_app_password,
        current_encrypted=raw.get("yandex_disk_app_password"),
    )
    if pw_changed:
        if pw_val is None:
            raw.pop("yandex_disk_app_password", None)
        else:
            raw["yandex_disk_app_password"] = pw_val
        changed.append("yandex_disk_app_password")

    # Path / retention: plain values.
    if body.yandex_disk_path is not None:
        if body.yandex_disk_path == "":
            if raw.pop("yandex_disk_path", None) is not None:
                changed.append("yandex_disk_path")
        else:
            if raw.get("yandex_disk_path") != body.yandex_disk_path:
                raw["yandex_disk_path"] = body.yandex_disk_path
                changed.append("yandex_disk_path")

    if body.retention_daily is not None:
        if raw.get("retention_daily") != body.retention_daily:
            raw["retention_daily"] = body.retention_daily
            changed.append("retention_daily")
    if body.retention_monthly is not None:
        if raw.get("retention_monthly") != body.retention_monthly:
            raw["retention_monthly"] = body.retention_monthly
            changed.append("retention_monthly")

    await save_raw(session, "backup", raw)
    await session.commit()

    log.info(
        "settings.updated",
        group="backup",
        user_id=admin.id,
        changed_keys=changed,
    )
    return await get_backup(session, admin)


__all__ = ["router", "resolver"]
