"""Pydantic v2 schemas for the Settings API (task 6.3).

Each group has a `Read` schema (response of GET, secrets returned as
``"***" + last4`` or ``None``) and a `Write` schema (body of PUT, with
sentinel semantics applied by the route handler).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceName = Literal["open_meteo", "nasa_power", "openweathermap"]

DEFAULT_PRIORITY: list[SourceName] = ["open_meteo", "nasa_power", "openweathermap"]
DEFAULT_ENABLED: dict[SourceName, bool] = {
    "open_meteo": True,
    "nasa_power": True,
    "openweathermap": False,
}


# ── Sources ──────────────────────────────────────────────────────────────────


class SourcesSettings(BaseModel):
    """Weather-source priority order, per-source enable flag, and average mode."""

    model_config = ConfigDict(extra="forbid")

    priority: list[SourceName] = Field(default_factory=lambda: list(DEFAULT_PRIORITY))
    enabled: dict[SourceName, bool] = Field(
        default_factory=lambda: dict(DEFAULT_ENABLED)
    )
    average_mode: bool = False


class SourcesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: list[SourceName] | None = None
    enabled: dict[SourceName, bool] | None = None
    average_mode: bool | None = None


# ── API keys ─────────────────────────────────────────────────────────────────


class ApiKeysRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openweathermap_api_key: str | None = None


class ApiKeysUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openweathermap_api_key: str | None = None


# ── Telegram ────────────────────────────────────────────────────────────────


class TelegramRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_token: str | None = None


class TelegramUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_token: str | None = None


# ── Backup ──────────────────────────────────────────────────────────────────


class BackupRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yandex_disk_login: str | None = None
    yandex_disk_app_password: str | None = None
    yandex_disk_path: str = "/weather-app-backups/"
    retention_daily: int = 30
    retention_monthly: int = 12


class BackupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    yandex_disk_login: str | None = None
    yandex_disk_app_password: str | None = None
    yandex_disk_path: str | None = None
    retention_daily: int | None = Field(default=None, ge=1, le=3650)
    retention_monthly: int | None = Field(default=None, ge=1, le=120)
