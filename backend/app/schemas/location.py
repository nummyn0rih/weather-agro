from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

LocationType = Literal["own", "purchase"]


def _validate_iana_tz(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {value!r}") from exc
    return value


class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    region: str | None = Field(None, max_length=100)
    type: LocationType
    note: str | None = None
    timezone: str = Field(
        "UTC",
        max_length=64,
        description="IANA timezone (e.g. 'Europe/Moscow'). Used for TZ-aware "
        "daily aggregation. Defaults to 'UTC'.",
    )

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, v: str) -> str:
        return _validate_iana_tz(v)


class LocationCreate(LocationBase):
    pass


class LocationUpdate(BaseModel):
    """Partial update — only fields explicitly set in the request body are applied."""

    name: str | None = Field(None, min_length=1, max_length=200)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    region: str | None = Field(None, max_length=100)
    type: LocationType | None = None
    note: str | None = None
    timezone: str | None = Field(None, max_length=64)

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_iana_tz(v)


class LocationResponse(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    import_status: Literal["pending", "in_progress", "done", "error"]
    import_progress: int


class LocationImportStatus(BaseModel):
    """Progress snapshot for the per-location history backfill task."""

    model_config = ConfigDict(from_attributes=True)

    location_id: int
    status: Literal["pending", "in_progress", "done", "error"]
    progress: int = Field(..., ge=0, le=100)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
