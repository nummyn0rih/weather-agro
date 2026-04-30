from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReportStatus = Literal["pending", "in_progress", "done", "error"]


class ReportGenerateRequest(BaseModel):
    location_id: int = Field(..., ge=1)
    season_year: int = Field(..., ge=1900, le=2100)


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: int | None
    season_year: int
    status: ReportStatus
    file_size_bytes: int | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
