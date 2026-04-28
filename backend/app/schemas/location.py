from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LocationType = Literal["own", "purchase"]


class LocationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    region: str | None = Field(None, max_length=100)
    type: LocationType
    note: str | None = None


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


class LocationResponse(LocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
