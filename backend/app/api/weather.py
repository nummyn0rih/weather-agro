from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.weather import (
    Aggregation,
    WeatherDailyPoint,
    WeatherSource,
)
from app.services.weather import query as query_service

router = APIRouter(prefix="/weather", tags=["weather"])
log = structlog.get_logger()


@router.get(
    "/daily",
    response_model=list[WeatherDailyPoint],
    summary="Universal daily weather query (per source or cross-source average)",
)
async def get_weather_daily(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_ids: Annotated[list[int], Query(min_length=1)],
    parameters: Annotated[list[str], Query(min_length=1)],
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    source: Annotated[WeatherSource, Query()] = "open_meteo",
    aggregation: Annotated[Aggregation, Query()] = "day",
) -> list[dict]:
    try:
        rows = await query_service.query_daily(
            session,
            location_ids=location_ids,
            parameters=parameters,
            date_from=date_from,
            date_to=date_to,
            source=source,
            aggregation=aggregation,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    log.info(
        "weather.daily.query",
        location_ids=location_ids,
        parameters=parameters,
        source=source,
        aggregation=aggregation,
        rows=len(rows),
    )
    return rows
