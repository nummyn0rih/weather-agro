from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EventType = Literal["planting", "harvest", "note"]


class EventWeather(BaseModel):
    """Weather snapshot attached to a field event (cross-source average for the event date)."""

    model_config = ConfigDict(extra="allow")

    temp_min: float | None = None
    temp_max: float | None = None
    temp_avg: float | None = None
    soil_temp_0: float | None = None
    soil_temp_7: float | None = None
    soil_temp_28: float | None = None
    soil_temp_100: float | None = None
    dew_point: float | None = None
    frost_hours: float | None = None
    humidity_min: float | None = None
    humidity_max: float | None = None
    humidity_avg: float | None = None
    soil_moisture_0_7: float | None = None
    soil_moisture_7_28: float | None = None
    soil_moisture_28_100: float | None = None
    precipitation: float | None = None
    et0: float | None = None
    solar_radiation: float | None = None
    sunshine_hours: float | None = None
    wind_speed_avg: float | None = None
    wind_speed_max: float | None = None
    vpd: float | None = None


class FieldEventBase(BaseModel):
    location_id: int
    event_type: EventType
    event_date: date
    crop_id: int | None = None
    variety: str | None = Field(None, max_length=100)
    area_hectares: float | None = Field(None, gt=0)
    yield_kg: float | None = Field(None, ge=0)
    quality_rating: int | None = Field(None, ge=1, le=5)
    description: str | None = None


class FieldEventCreate(FieldEventBase):
    @model_validator(mode="after")
    def _validate_type_specific(self) -> "FieldEventCreate":
        if self.event_type == "planting" and self.crop_id is None:
            raise ValueError("crop_id is required for planting events")
        if self.event_type == "harvest":
            if self.crop_id is None:
                raise ValueError("crop_id is required for harvest events")
            if self.yield_kg is None:
                raise ValueError("yield_kg is required for harvest events")
        return self


class FieldEventUpdate(BaseModel):
    """Partial update — only fields explicitly set in the request body are applied."""

    location_id: int | None = None
    event_type: EventType | None = None
    event_date: date | None = None
    crop_id: int | None = None
    variety: str | None = Field(None, max_length=100)
    area_hectares: float | None = Field(None, gt=0)
    yield_kg: float | None = Field(None, ge=0)
    quality_rating: int | None = Field(None, ge=1, le=5)
    description: str | None = None


class FieldEventResponse(FieldEventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    photos: list[str]
    created_at: datetime
    weather: EventWeather | None = None
