"""Pure command handlers used by the Telegram bot.

The handlers are decoupled from python-telegram-bot's ``Update`` /
``Context`` objects so they can be unit-tested without spinning up a real
bot. Each handler takes an :class:`AsyncSession`, the originating
``chat_id`` and any user-supplied arguments, and returns the text to send
back. Command-line dispatch lives in :mod:`app.telegram_bot.main`.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AlertHistory,
    AlertRule,
    Location,
    User,
    WeatherDaily,
    WeatherForecast,
)
from app.services import telegram_bind

HELP_TEXT = (
    "🌾 <b>Weather Agro bot</b>\n\n"
    "Команды:\n"
    "/start &lt;код&gt; — привязать чат (код берётся в UI)\n"
    "/help — эта справка\n"
    "/locations — список локаций\n"
    "/weather &lt;id&gt; — погода вчера\n"
    "/forecast &lt;id&gt; — прогноз на 7 дней\n"
    "/alerts — активные правила алертов\n"
    "/alerts_history — последние срабатывания\n"
    "/stats &lt;id&gt; &lt;период&gt; — например /stats 3 7d"
)


_PERIOD_RE = re.compile(r"^(\d+)([dwmy])$")


def parse_period(period: str) -> int:
    """Parse e.g. ``7d``, ``2w``, ``3m``, ``1y`` into a number of days."""
    match = _PERIOD_RE.match(period.strip().lower())
    if not match:
        raise ValueError(f"Bad period: {period!r}. Use e.g. 7d, 2w, 1m, 1y.")
    n = int(match.group(1))
    unit = match.group(2)
    if n <= 0:
        raise ValueError("Period must be positive.")
    return n * {"d": 1, "w": 7, "m": 30, "y": 365}[unit]


async def _ensure_bound(
    session: AsyncSession, chat_id: int
) -> User | None:
    return await telegram_bind.get_user_by_chat_id(session, chat_id)


def _format_value(v: float | None, unit: str = "", digits: int = 1) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}{unit}"


async def handle_start(
    session: AsyncSession,
    chat_id: int,
    args: Sequence[str],
    *,
    now: datetime | None = None,
) -> str:
    if not args:
        return (
            "Чтобы привязать этот чат, сгенерируй код в UI и пришли:\n"
            "<code>/start &lt;код&gt;</code>"
        )
    code = args[0].strip()
    user = await telegram_bind.consume_bind_code(session, code, chat_id, now=now)
    if user is None:
        return "❌ Неверный или просроченный код."
    return f"✅ Чат привязан к пользователю <b>{user.username}</b>."


async def handle_help(
    session: AsyncSession, chat_id: int, args: Sequence[str]
) -> str:
    return HELP_TEXT


async def handle_locations(
    session: AsyncSession, chat_id: int, args: Sequence[str]
) -> str:
    user = await _ensure_bound(session, chat_id)
    if user is None:
        return "🔒 Чат не привязан. Используй /start &lt;код&gt;."
    rows = (
        await session.execute(select(Location).order_by(Location.id))
    ).scalars().all()
    if not rows:
        return "Локаций нет."
    lines = ["📍 <b>Локации</b>"]
    for loc in rows:
        region = f", {loc.region}" if loc.region else ""
        lines.append(f"<code>{loc.id}</code> — {loc.name} ({loc.type}{region})")
    return "\n".join(lines)


async def _latest_daily(
    session: AsyncSession, location_id: int
) -> tuple[WeatherDaily | None, date | None]:
    stmt = (
        select(WeatherDaily)
        .where(WeatherDaily.location_id == location_id)
        .order_by(desc(WeatherDaily.time))
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return row, row.time if row else None


async def handle_weather(
    session: AsyncSession, chat_id: int, args: Sequence[str]
) -> str:
    user = await _ensure_bound(session, chat_id)
    if user is None:
        return "🔒 Чат не привязан. Используй /start &lt;код&gt;."
    if not args:
        return "Использование: <code>/weather &lt;id&gt;</code>"
    try:
        location_id = int(args[0])
    except ValueError:
        return "❌ id локации должен быть числом."
    location = await session.get(Location, location_id)
    if location is None:
        return f"❌ Локация {location_id} не найдена."
    row, day = await _latest_daily(session, location_id)
    if row is None or day is None:
        return f"Для локации {location.name} нет данных."
    return (
        f"🌡 <b>{location.name}</b> — {day.isoformat()}\n"
        f"Темп.: {_format_value(row.temp_min, '°C')} … "
        f"{_format_value(row.temp_max, '°C')} (ср. {_format_value(row.temp_avg, '°C')})\n"
        f"Влажн.: {_format_value(row.humidity_avg, '%')}\n"
        f"Осадки: {_format_value(row.precipitation, ' мм')}\n"
        f"Ветер: {_format_value(row.wind_speed_avg, ' м/с')}"
    )


async def handle_forecast(
    session: AsyncSession,
    chat_id: int,
    args: Sequence[str],
    *,
    now: datetime | None = None,
) -> str:
    user = await _ensure_bound(session, chat_id)
    if user is None:
        return "🔒 Чат не привязан. Используй /start &lt;код&gt;."
    if not args:
        return "Использование: <code>/forecast &lt;id&gt;</code>"
    try:
        location_id = int(args[0])
    except ValueError:
        return "❌ id локации должен быть числом."
    location = await session.get(Location, location_id)
    if location is None:
        return f"❌ Локация {location_id} не найдена."

    today = (now or datetime.now(UTC)).date()
    end = today + timedelta(days=7)
    stmt = (
        select(WeatherForecast)
        .where(
            WeatherForecast.location_id == location_id,
            WeatherForecast.time >= today,
            WeatherForecast.time <= end,
        )
        .order_by(WeatherForecast.time)
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return f"Прогноза для {location.name} нет."

    # Average across sources per day.
    by_day: dict[date, list[WeatherForecast]] = {}
    for r in rows:
        by_day.setdefault(r.time, []).append(r)

    def _avg(rs: Sequence[WeatherForecast], col: str) -> float | None:
        vs = [v for r in rs if (v := getattr(r, col)) is not None]
        return sum(vs) / len(vs) if vs else None

    lines = [f"📅 <b>Прогноз — {location.name}</b>"]
    for d in sorted(by_day):
        rs = by_day[d]
        lines.append(
            f"{d.isoformat()}: "
            f"{_format_value(_avg(rs, 'temp_min'), '°')}…"
            f"{_format_value(_avg(rs, 'temp_max'), '°')}, "
            f"осадки {_format_value(_avg(rs, 'precipitation'), ' мм')}"
        )
    return "\n".join(lines)


async def handle_alerts(
    session: AsyncSession, chat_id: int, args: Sequence[str]
) -> str:
    user = await _ensure_bound(session, chat_id)
    if user is None:
        return "🔒 Чат не привязан. Используй /start &lt;код&gt;."
    rows = (
        await session.execute(
            select(AlertRule)
            .where(AlertRule.enabled.is_(True))
            .order_by(AlertRule.id)
        )
    ).scalars().all()
    if not rows:
        return "Активных правил нет."
    lines = ["🚨 <b>Активные правила</b>"]
    for r in rows:
        cond = r.condition
        if cond == "between":
            cond_str = f"∈ [{r.threshold:g}, {r.threshold_max:g}]"
        else:
            op = {"gt": ">", "lt": "<", "eq": "="}.get(cond, cond)
            cond_str = f"{op} {r.threshold:g}"
        lines.append(f"<code>{r.id}</code> — {r.name}: {r.parameter} {cond_str}")
    return "\n".join(lines)


async def handle_alerts_history(
    session: AsyncSession, chat_id: int, args: Sequence[str]
) -> str:
    user = await _ensure_bound(session, chat_id)
    if user is None:
        return "🔒 Чат не привязан. Используй /start &lt;код&gt;."
    rows = (
        await session.execute(
            select(AlertHistory)
            .order_by(desc(AlertHistory.triggered_at))
            .limit(10)
        )
    ).scalars().all()
    if not rows:
        return "Срабатываний нет."
    lines = ["📜 <b>Последние срабатывания</b>"]
    for h in rows:
        lines.append(
            f"{h.triggered_at:%Y-%m-%d %H:%M}: {h.message}"
        )
    return "\n".join(lines)


async def handle_stats(
    session: AsyncSession,
    chat_id: int,
    args: Sequence[str],
    *,
    now: datetime | None = None,
) -> str:
    user = await _ensure_bound(session, chat_id)
    if user is None:
        return "🔒 Чат не привязан. Используй /start &lt;код&gt;."
    if len(args) < 2:
        return "Использование: <code>/stats &lt;id&gt; &lt;период&gt;</code> (например, /stats 3 7d)"
    try:
        location_id = int(args[0])
    except ValueError:
        return "❌ id локации должен быть числом."
    try:
        days = parse_period(args[1])
    except ValueError as exc:
        return f"❌ {exc}"

    location = await session.get(Location, location_id)
    if location is None:
        return f"❌ Локация {location_id} не найдена."

    today = (now or datetime.now(UTC)).date()
    start = today - timedelta(days=days)
    stmt = select(WeatherDaily).where(
        WeatherDaily.location_id == location_id,
        WeatherDaily.time >= start,
        WeatherDaily.time <= today,
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return f"Нет данных для {location.name} за {args[1]}."

    def _vals(col: str) -> list[float]:
        return [v for r in rows if (v := getattr(r, col)) is not None]

    tmin = _vals("temp_min")
    tmax = _vals("temp_max")
    tavg = _vals("temp_avg")
    prcp = _vals("precipitation")
    return (
        f"📊 <b>{location.name}</b> — {args[1]}\n"
        f"Темп. мин: {_format_value(min(tmin) if tmin else None, '°C')}\n"
        f"Темп. макс: {_format_value(max(tmax) if tmax else None, '°C')}\n"
        f"Темп. ср.: "
        f"{_format_value(sum(tavg) / len(tavg) if tavg else None, '°C')}\n"
        f"Сумма осадков: {_format_value(sum(prcp) if prcp else None, ' мм')}"
    )
