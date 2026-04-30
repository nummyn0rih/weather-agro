from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AlertRule
from app.schemas.alert import AlertRuleCreate, AlertRuleUpdate


async def list_rules(
    session: AsyncSession,
    enabled: bool | None = None,
) -> Sequence[AlertRule]:
    stmt = select(AlertRule)
    if enabled is not None:
        stmt = stmt.where(AlertRule.enabled == enabled)
    stmt = stmt.order_by(AlertRule.id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_rule(session: AsyncSession, rule_id: int) -> AlertRule | None:
    result = await session.execute(select(AlertRule).where(AlertRule.id == rule_id))
    return result.scalar_one_or_none()


async def create_rule(session: AsyncSession, data: AlertRuleCreate) -> AlertRule:
    obj = AlertRule(**data.model_dump())
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def update_rule(
    session: AsyncSession, rule_id: int, data: AlertRuleUpdate
) -> AlertRule | None:
    obj = await get_rule(session, rule_id)
    if not obj:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    await session.commit()
    await session.refresh(obj)
    return obj


async def delete_rule(session: AsyncSession, rule_id: int) -> bool:
    obj = await get_rule(session, rule_id)
    if not obj:
        return False
    await session.delete(obj)
    await session.commit()
    return True
