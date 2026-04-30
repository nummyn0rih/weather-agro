from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AlertParameter = Literal[
    "temperature_avg",
    "temperature_min",
    "temperature_max",
    "precipitation",
    "humidity_avg",
    "wind_speed_avg",
    "wind_speed_max",
    "pressure_avg",
    "vpd_avg",
    "soil_moisture_avg",
    "soil_temperature_avg",
]
AlertCondition = Literal["gt", "lt", "eq", "between"]


class AlertRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    parameter: AlertParameter
    condition: AlertCondition
    threshold: float
    threshold_max: float | None = None
    location_ids: list[int] = Field(default_factory=list)
    enabled: bool = True
    telegram: bool = True

    @model_validator(mode="after")
    def _validate_between(self) -> "AlertRuleBase":
        if self.condition == "between":
            if self.threshold_max is None:
                raise ValueError("threshold_max is required when condition is 'between'")
            if self.threshold_max <= self.threshold:
                raise ValueError("threshold_max must be greater than threshold")
        return self


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    """Partial update — only fields explicitly set are applied."""

    name: str | None = Field(None, min_length=1, max_length=200)
    parameter: AlertParameter | None = None
    condition: AlertCondition | None = None
    threshold: float | None = None
    threshold_max: float | None = None
    location_ids: list[int] | None = None
    enabled: bool | None = None
    telegram: bool | None = None


class AlertRuleResponse(AlertRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class AlertHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_id: int | None
    rule_name: str
    location_id: int | None
    location_name: str
    parameter: str
    condition: str
    threshold: float
    threshold_max: float | None
    value: float
    triggered_at: datetime
    message: str


class AlertHistoryResponse(BaseModel):
    items: list[AlertHistoryItem]
    total: int
    limit: int
    offset: int
