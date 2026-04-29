from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

NormalPeriod = Literal["month", "week", "doy"]
AnomalyLevel = Literal["none", "moderate", "extreme"]


class ClimateNormalRow(BaseModel):
    """One cached climate-normal bucket for (location, parameter, period)."""

    model_config = ConfigDict(from_attributes=True)

    location_id: int
    parameter: str
    period: NormalPeriod
    bucket: int
    mean: float | None
    std: float | None
    min: float | None
    max: float | None
    count: int
    year_from: int | None
    year_to: int | None
    updated_at: datetime | None = None


class AnomalyRow(BaseModel):
    """One day's deviation from the matching climate-normal bucket."""

    time: date
    location_id: int
    parameter: str
    value: float | None
    normal_mean: float | None
    normal_std: float | None
    deviation: float | None
    sigma: float | None
    level: AnomalyLevel
    bucket: int
    period: NormalPeriod
