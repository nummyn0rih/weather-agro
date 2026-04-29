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
    CumulativeParameter,
    CumulativePoint,
    HeatmapCell,
    HeatmapXAxis,
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
    compare_years: Annotated[
        list[int] | None,
        Query(description="If set, overlay the date_from..date_to MM-DD window across these years."),
    ] = None,
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
            compare_years=compare_years,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    log.info(
        "weather.daily.query",
        location_ids=location_ids,
        parameters=parameters,
        source=source,
        aggregation=aggregation,
        compare_years=compare_years,
        rows=len(rows),
    )
    return rows


@router.get(
    "/heatmap",
    response_model=list[HeatmapCell],
    summary="Heatmap matrix (year x month/week/doy) for one parameter at one location",
)
async def get_weather_heatmap(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_id: Annotated[int, Query()],
    parameter: Annotated[str, Query()],
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    source: Annotated[WeatherSource, Query()] = "open_meteo",
    axis: Annotated[HeatmapXAxis, Query()] = "month",
) -> list[dict]:
    try:
        cells = await query_service.query_heatmap(
            session,
            location_id=location_id,
            parameter=parameter,
            date_from=date_from,
            date_to=date_to,
            source=source,
            axis=axis,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    log.info(
        "weather.heatmap.query",
        location_id=location_id,
        parameter=parameter,
        source=source,
        axis=axis,
        cells=len(cells),
    )
    return cells


@router.get(
    "/cumulative",
    response_model=list[CumulativePoint],
    summary="Running cumulative sums (precipitation, et0, sunshine_hours, GDD)",
)
async def get_weather_cumulative(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_ids: Annotated[list[int], Query(min_length=1)],
    parameter: Annotated[CumulativeParameter, Query()],
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    source: Annotated[WeatherSource, Query()] = "open_meteo",
    base_temperature: Annotated[
        float | None,
        Query(description="Required when parameter='gdd'. Crop-specific base temperature in °C."),
    ] = None,
) -> list[dict]:
    try:
        rows = await query_service.query_cumulative(
            session,
            location_ids=location_ids,
            parameter=parameter,
            date_from=date_from,
            date_to=date_to,
            source=source,
            base_temperature=base_temperature,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    log.info(
        "weather.cumulative.query",
        location_ids=location_ids,
        parameter=parameter,
        source=source,
        base_temperature=base_temperature,
        rows=len(rows),
    )
    return rows
