from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.alert_history import router as alert_history_router
from app.api.alerts import router as alerts_router
from app.api.analytics import router as analytics_router
from app.api.auth import limiter as auth_limiter
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.locations import router as locations_router
from app.api.weather import router as weather_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.scheduler import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = structlog.get_logger()
    settings = get_settings()
    log.info("app.startup", environment=settings.ENVIRONMENT, log_level=settings.LOG_LEVEL)

    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    log.info("scheduler.started", jobs=[j.id for j in scheduler.get_jobs()])

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
        log.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Weather Agro API",
        version="0.1.0",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = auth_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(locations_router, prefix="/api")
    app.include_router(weather_router, prefix="/api")
    app.include_router(analytics_router, prefix="/api")
    app.include_router(alerts_router, prefix="/api")
    app.include_router(alert_history_router, prefix="/api")

    return app


app = create_app()
