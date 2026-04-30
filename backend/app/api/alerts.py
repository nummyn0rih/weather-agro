from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import AlertRule, User
from app.db.session import get_db
from app.schemas.alert import (
    AlertRuleBase,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)
from app.services.alerts import rules as rules_service

router = APIRouter(prefix="/alerts/rules", tags=["alerts"])
log = structlog.get_logger()


@router.get(
    "",
    response_model=list[AlertRuleResponse],
    summary="List alert rules",
)
async def list_rules(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
    enabled: Annotated[bool | None, Query()] = None,
) -> list[AlertRule]:
    items = await rules_service.list_rules(session, enabled=enabled)
    return list(items)


@router.post(
    "",
    response_model=AlertRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create alert rule",
)
async def create_rule(
    body: AlertRuleCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> AlertRule:
    obj = await rules_service.create_rule(session, body)
    log.info("alert_rule.created", id=obj.id, name=obj.name)
    return obj


@router.get(
    "/{rule_id}",
    response_model=AlertRuleResponse,
    summary="Get alert rule by ID",
)
async def get_rule(
    rule_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> AlertRule:
    obj = await rules_service.get_rule(session, rule_id)
    if not obj:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert rule not found")
    return obj


@router.put(
    "/{rule_id}",
    response_model=AlertRuleResponse,
    summary="Partial update of alert rule",
)
async def update_rule(
    rule_id: int,
    body: AlertRuleUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> AlertRule:
    existing = await rules_service.get_rule(session, rule_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert rule not found")

    merged = {
        "name": existing.name,
        "parameter": existing.parameter,
        "condition": existing.condition,
        "threshold": existing.threshold,
        "threshold_max": existing.threshold_max,
        "location_ids": existing.location_ids,
        "enabled": existing.enabled,
        "telegram": existing.telegram,
        **body.model_dump(exclude_unset=True),
    }
    try:
        AlertRuleBase.model_validate(merged)
    except ValidationError as exc:
        errors = [
            {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
            for e in exc.errors()
        ]
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, errors) from exc

    obj = await rules_service.update_rule(session, rule_id, body)
    assert obj is not None
    log.info("alert_rule.updated", id=rule_id)
    return obj


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete alert rule",
)
async def delete_rule(
    rule_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> None:
    deleted = await rules_service.delete_rule(session, rule_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert rule not found")
    log.info("alert_rule.deleted", id=rule_id)
