from pydantic import BaseModel, ConfigDict


class CropResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_temperature: float
    optimal_temp_min: float | None = None
    optimal_temp_max: float | None = None
