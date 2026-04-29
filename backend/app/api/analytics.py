from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.analytics import (
    AnomalyRow,
    ClimateNormalRow,
    CorrelationMatrix,
    NormalPeriod,
)
from app.schemas.weather import WeatherSource
from app.services.analytics import anomalies as anomalies_service
from app.services.analytics import climate_normals as normals_service
from app.services.analytics import correlations as correlations_service

router = APIRouter(prefix="/analytics", tags=["analytics"])
log = structlog.get_logger()


@router.get(
    "/normals",
    response_model=list[ClimateNormalRow],
    summary="Climate normals (multi-year mean/std/min/max) per period bucket",
)
async def get_climate_normals(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_id: Annotated[int, Query()],
    parameter: Annotated[str, Query()],
    period: Annotated[NormalPeriod, Query()] = "month",
    refresh: Annotated[
        bool,
        Query(description="If true, recompute from raw weather_daily and update cache."),
    ] = False,
) -> list[dict]:
    try:
        if refresh:
            rows = await normals_service.calculate_normals(
                session,
                location_id=location_id,
                parameter=parameter,
                period=period,
            )
            await normals_service.upsert_normals(
                session,
                location_id=location_id,
                parameter=parameter,
                period=period,
                rows=rows,
            )
            log.info(
                "analytics.normals.refresh",
                location_id=location_id,
                parameter=parameter,
                period=period,
                rows=len(rows),
            )
            return rows

        cached = await normals_service.get_cached_normals(
            session,
            location_id=location_id,
            parameter=parameter,
            period=period,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    log.info(
        "analytics.normals.read",
        location_id=location_id,
        parameter=parameter,
        period=period,
        rows=len(cached),
    )
    return [
        {
            "location_id": r.location_id,
            "parameter": r.parameter,
            "period": r.period,
            "bucket": r.bucket,
            "mean": r.mean,
            "std": r.std,
            "min": r.min,
            "max": r.max,
            "count": r.count,
            "year_from": r.year_from,
            "year_to": r.year_to,
            "updated_at": r.updated_at,
        }
        for r in cached
    ]


@router.get(
    "/anomalies",
    response_model=list[AnomalyRow],
    summary="Daily deviations from cached climate normals (none / >1σ / >2σ)",
)
async def get_anomalies(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_id: Annotated[int, Query()],
    parameter: Annotated[str, Query()],
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    period: Annotated[NormalPeriod, Query()] = "month",
    source: Annotated[WeatherSource, Query()] = "average",
) -> list[dict]:
    try:
        rows = await anomalies_service.get_anomalies(
            session,
            location_id=location_id,
            parameter=parameter,
            date_from=date_from,
            date_to=date_to,
            period=period,
            source=source,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    log.info(
        "analytics.anomalies",
        location_id=location_id,
        parameter=parameter,
        period=period,
        source=source,
        rows=len(rows),
    )
    return rows


@router.get(
    "/correlations",
    response_model=CorrelationMatrix,
    summary="Pearson correlation matrix between weather parameters",
)
async def get_correlations(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_id: Annotated[int, Query()],
    parameters: Annotated[
        list[str],
        Query(
            description=(
                "Weather parameters to correlate. Pass 2+ values, e.g. "
                "?parameters=temp_avg&parameters=precipitation."
            )
        ),
    ],
    date_from: Annotated[date, Query()],
    date_to: Annotated[date, Query()],
    source: Annotated[WeatherSource, Query()] = "average",
) -> dict:
    try:
        result = await correlations_service.get_correlations(
            session,
            location_id=location_id,
            parameters=parameters,
            date_from=date_from,
            date_to=date_to,
            source=source,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    log.info(
        "analytics.correlations",
        location_id=location_id,
        parameters=result["parameters"],
        source=source,
        n=result["n"],
    )
    return result
