"""Alert history query service.

Reads from ``alert_history`` with snapshot-only fields (rule data lives in the
snapshot columns, so the AlertRule relationship is intentionally not loaded).
``Location`` is eager-loaded via ``selectinload`` so the API can render
``location_name`` without a per-row roundtrip.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AlertHistory


async def query_history(
    session: AsyncSession,
    *,
    location_id: int | None = None,
    rule_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[Sequence[AlertHistory], int]:
    """Return a page of ``AlertHistory`` rows plus the total matching count.

    ``date_from`` is inclusive at 00:00 UTC; ``date_to`` is inclusive (the
    filter expands to ``< date_to + 1 day`` 00:00 UTC). Rows are ordered by
    ``triggered_at DESC``. ``Location`` is eager-loaded.
    """
    filters = []
    if location_id is not None:
        filters.append(AlertHistory.location_id == location_id)
    if rule_id is not None:
        filters.append(AlertHistory.rule_id == rule_id)
    if date_from is not None:
        filters.append(
            AlertHistory.triggered_at
            >= datetime.combine(date_from, datetime.min.time(), tzinfo=UTC)
        )
    if date_to is not None:
        filters.append(
            AlertHistory.triggered_at
            < datetime.combine(
                date_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC
            )
        )

    count_stmt = select(func.count(AlertHistory.id))
    if filters:
        count_stmt = count_stmt.where(*filters)
    total = (await session.execute(count_stmt)).scalar_one()

    items_stmt = select(AlertHistory)
    if filters:
        items_stmt = items_stmt.where(*filters)
    items_stmt = (
        items_stmt.options(selectinload(AlertHistory.location))
        .order_by(AlertHistory.triggered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = (await session.execute(items_stmt)).scalars().all()
    return items, int(total)
