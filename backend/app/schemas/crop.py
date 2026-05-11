from pydantic import BaseModel, ConfigDict, Field


class CropResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_temperature: float
    optimal_temp_min: float | None = None
    optimal_temp_max: float | None = None


class CropCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_temperature: float
    optimal_temp_min: float | None = None
    optimal_temp_max: float | None = None


class CropUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    base_temperature: float | None = None
    optimal_temp_min: float | None = None
    optimal_temp_max: float | None = None
