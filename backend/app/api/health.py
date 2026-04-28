import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])
log = structlog.get_logger()


class HealthResponse(BaseModel):
    status: str = Field(..., examples=["ok"])
    environment: str = Field(..., examples=["development"])
    version: str = Field(..., examples=["0.1.0"])
    database: str = Field(..., examples=["ok", "down"])


async def _check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        log.warning("health.db_check_failed", error=str(exc))
        return False


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health check",
    description="Liveness probe with DB connectivity check. "
    "Always returns HTTP 200; `database` field reports `ok` or `down`.",
)
async def health() -> HealthResponse:
    settings = get_settings()
    db_ok = await _check_database()
    return HealthResponse(
        status="ok",
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        database="ok" if db_ok else "down",
    )
