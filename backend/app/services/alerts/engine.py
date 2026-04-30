"""Alert rule evaluation engine.

The engine reads ``weather_daily`` for ``target_day`` (defaulting to
yesterday in UTC), averages each rule's parameter across the available
sources for every location the rule targets, evaluates the rule's
condition, and writes an :class:`AlertHistory` row when it fires.

Repeat alerts for the same ``(rule_id, location_id)`` are suppressed for
``dedup_hours`` after the most recent trigger.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AlertHistory, AlertRule, Location, WeatherDaily

NotifierFn = Callable[[AlertRule, AlertHistory], Awaitable[None]]

logger = structlog.get_logger(__name__)

DEFAULT_DEDUP_HOURS = 6

# Map AlertParameter values to columns on weather_daily. When several
# columns are listed (e.g. soil_moisture across depths), each column is
# averaged across sources first, then averaged together.
PARAMETER_COLUMNS: dict[str, tuple[str, ...]] = {
    "temperature_avg": ("temp_avg",),
    "temperature_min": ("temp_min",),
    "temperature_max": ("temp_max",),
    "precipitation": ("precipitation",),
    "humidity_avg": ("humidity_avg",),
    "wind_speed_avg": ("wind_speed_avg",),
    "wind_speed_max": ("wind_speed_max",),
    "vpd_avg": ("vpd",),
    "soil_moisture_avg": (
        "soil_moisture_0_7",
        "soil_moisture_7_28",
        "soil_moisture_28_100",
    ),
    "soil_temperature_avg": (
        "soil_temp_0",
        "soil_temp_7",
        "soil_temp_28",
        "soil_temp_100",
    ),
    "pressure_avg": (),
}


def check_condition(
    value: float,
    condition: str,
    threshold: float,
    threshold_max: float | None = None,
) -> bool:
    """Return True if ``value`` satisfies the rule's condition."""
    if condition == "gt":
        return value > threshold
    if condition == "lt":
        return value < threshold
    if condition == "eq":
        return math.isclose(value, threshold, abs_tol=1e-3)
    if condition == "between":
        if threshold_max is None:
            return False
        return threshold <= value <= threshold_max
    return False


def _mean(xs: Sequence[float]) -> float | None:
    return statistics.fmean(xs) if xs else None


async def _resolve_location_ids(session: AsyncSession, rule: AlertRule) -> list[int]:
    if rule.location_ids:
        return list(rule.location_ids)
    result = await session.execute(select(Location.id))
    return list(result.scalars().all())


async def _aggregate_value(
    session: AsyncSession,
    location_id: int,
    target_day: date,
    columns: Sequence[str],
) -> float | None:
    if not columns:
        return None
    stmt = select(WeatherDaily).where(
        WeatherDaily.location_id == location_id,
        WeatherDaily.time == target_day,
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return None
    per_column: list[float] = []
    for col in columns:
        per_source: list[float] = [
            v for r in rows if (v := getattr(r, col, None)) is not None
        ]
        m = _mean(per_source)
        if m is not None:
            per_column.append(m)
    return _mean(per_column)


async def _last_triggered_at(
    session: AsyncSession, rule_id: int, location_id: int
) -> datetime | None:
    stmt = (
        select(AlertHistory.triggered_at)
        .where(
            AlertHistory.rule_id == rule_id,
            AlertHistory.location_id == location_id,
        )
        .order_by(desc(AlertHistory.triggered_at))
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _format_message(rule: AlertRule, value: float, location_id: int) -> str:
    if rule.condition == "between":
        return (
            f"{rule.name}: {rule.parameter}={value:.2f} ∈ "
            f"[{rule.threshold:.2f}, {rule.threshold_max:.2f}] "
            f"(location_id={location_id})"
        )
    op = {"gt": ">", "lt": "<", "eq": "="}.get(rule.condition, rule.condition)
    return (
        f"{rule.name}: {rule.parameter}={value:.2f} {op} "
        f"{rule.threshold:.2f} (location_id={location_id})"
    )


async def evaluate_rule(
    session: AsyncSession,
    rule: AlertRule,
    *,
    target_day: date,
    now: datetime | None = None,
    dedup_hours: int = DEFAULT_DEDUP_HOURS,
    notifier: NotifierFn | None = None,
) -> list[AlertHistory]:
    """Evaluate one rule. Returns the AlertHistory rows it created.

    If ``notifier`` is provided, it is invoked once per created row after
    the rows are committed. Notifier failures are logged but do not affect
    the returned history.
    """
    if not rule.enabled:
        return []

    columns = PARAMETER_COLUMNS.get(rule.parameter, ())
    if not columns:
        logger.warning(
            "alerts.parameter_unsupported",
            rule_id=rule.id,
            parameter=rule.parameter,
        )
        return []

    moment = now or datetime.now(UTC)
    cutoff = moment - timedelta(hours=dedup_hours)
    location_ids = await _resolve_location_ids(session, rule)

    created: list[AlertHistory] = []
    for loc_id in location_ids:
        value = await _aggregate_value(session, loc_id, target_day, columns)
        if value is None:
            continue
        if not check_condition(
            value, rule.condition, rule.threshold, rule.threshold_max
        ):
            continue
        last = await _last_triggered_at(session, rule.id, loc_id)
        if last is not None and last >= cutoff:
            logger.info(
                "alerts.dedup_skip",
                rule_id=rule.id,
                location_id=loc_id,
                last=last.isoformat(),
            )
            continue
        history = AlertHistory(
            rule_id=rule.id,
            location_id=loc_id,
            triggered_at=moment,
            value=value,
            message=_format_message(rule, value, loc_id),
        )
        session.add(history)
        created.append(history)

    if created:
        await session.commit()
        for h in created:
            await session.refresh(h)
        if notifier is not None:
            for h in created:
                try:
                    await notifier(rule, h)
                except Exception:
                    logger.exception(
                        "alerts.notify_failed",
                        rule_id=rule.id,
                        history_id=h.id,
                    )
    return created


async def evaluate_all(
    session: AsyncSession,
    *,
    target_day: date | None = None,
    now: datetime | None = None,
    dedup_hours: int = DEFAULT_DEDUP_HOURS,
    notifier: NotifierFn | None = None,
) -> int:
    """Evaluate every enabled rule. Returns total triggers recorded."""
    moment = now or datetime.now(UTC)
    day = target_day or (moment.date() - timedelta(days=1))
    rules = (
        (await session.execute(select(AlertRule).where(AlertRule.enabled.is_(True))))
        .scalars()
        .all()
    )
    total = 0
    for rule in rules:
        try:
            created = await evaluate_rule(
                session,
                rule,
                target_day=day,
                now=moment,
                dedup_hours=dedup_hours,
                notifier=notifier,
            )
            total += len(created)
        except Exception:
            logger.exception("alerts.rule_evaluation_failed", rule_id=rule.id)
    return total
