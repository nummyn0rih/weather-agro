from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    environment: str = Field(..., examples=["development"])
    version: str = Field(..., examples=["0.1.0"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health check",
    description="Liveness probe. Returns app status, environment, and version. "
    "Database connectivity check lands in task 1.2.",
)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", environment=settings.ENVIRONMENT, version="0.1.0")
