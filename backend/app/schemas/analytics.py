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


class CorrelationMatrix(BaseModel):
    """Pearson correlation matrix between requested parameters.

    ``matrix[i][j]`` holds the Pearson coefficient between parameters[i] and
    parameters[j]; ``None`` when the paired sample has fewer than 2 valid
    observations or one of the series has zero variance. ``counts[i][j]`` is
    the number of paired observations actually used for that cell.
    """

    parameters: list[str]
    matrix: list[list[float | None]]
    counts: list[list[int]]
    n: int
