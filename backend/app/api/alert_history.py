from datetime import date
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.alert import AlertHistoryItem, AlertHistoryResponse
from app.services.alerts import history as history_service

router = APIRouter(prefix="/alerts/history", tags=["alerts"])
log = structlog.get_logger()

DELETED_LOCATION_LABEL = "(удалена)"


@router.get(
    "",
    response_model=AlertHistoryResponse,
    summary="Alert trigger history (filterable, paginated)",
)
async def list_history(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    location_id: Annotated[int | None, Query()] = None,
    rule_id: Annotated[int | None, Query()] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AlertHistoryResponse:
    rows, total = await history_service.query_history(
        session,
        location_id=location_id,
        rule_id=rule_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    log.info(
        "alert_history.list",
        total=total,
        returned=len(rows),
        limit=limit,
        offset=offset,
        location_id=location_id,
        rule_id=rule_id,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
    )
    items = [
        AlertHistoryItem(
            id=h.id,
            rule_id=h.rule_id,
            rule_name=h.rule_name_snapshot,
            location_id=h.location_id,
            location_name=h.location.name if h.location else DELETED_LOCATION_LABEL,
            parameter=h.parameter_snapshot,
            condition=h.condition_snapshot,
            threshold=h.threshold_snapshot,
            threshold_max=h.threshold_max_snapshot,
            value=h.value,
            triggered_at=h.triggered_at,
            message=h.message,
        )
        for h in rows
    ]
    return AlertHistoryResponse(
        items=items, total=total, limit=limit, offset=offset
    )
