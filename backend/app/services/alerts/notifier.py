"""Telegram notification dispatch for alert triggers.

When the alert engine creates an :class:`AlertHistory` row, this module
formats a message and sends it to every Telegram chat bound to a user.
Each ``sendMessage`` call is retried up to 3 times with exponential
backoff via tenacity. Per-chat send failures are logged but do not
prevent delivery to other chats.
"""

from __future__ import annotations

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.db.models import AlertHistory, AlertRule, Location, User

logger = structlog.get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
SEND_TIMEOUT_SECONDS = 10.0
MAX_SEND_ATTEMPTS = 3

PARAMETER_EMOJI: dict[str, str] = {
    "temperature_avg": "🌡",
    "temperature_min": "❄️",
    "temperature_max": "🔥",
    "precipitation": "🌧",
    "humidity_avg": "💧",
    "wind_speed_avg": "🌬",
    "wind_speed_max": "🌪",
    "vpd_avg": "🍃",
    "soil_moisture_avg": "🪴",
    "soil_temperature_avg": "🌱",
    "pressure_avg": "🧭",
}

PARAMETER_UNIT: dict[str, str] = {
    "temperature_avg": "°C",
    "temperature_min": "°C",
    "temperature_max": "°C",
    "precipitation": " мм",
    "humidity_avg": "%",
    "wind_speed_avg": " м/с",
    "wind_speed_max": " м/с",
    "vpd_avg": " кПа",
    "soil_moisture_avg": " м³/м³",
    "soil_temperature_avg": "°C",
    "pressure_avg": " гПа",
}


def format_alert_message(
    rule: AlertRule, history: AlertHistory, location_name: str
) -> str:
    """Render Telegram message: emoji + location + parameter + value + time."""
    emoji = PARAMETER_EMOJI.get(rule.parameter, "🚨")
    unit = PARAMETER_UNIT.get(rule.parameter, "")
    when = history.triggered_at.strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{emoji} <b>{rule.name}</b>\n"
        f"📍 {location_name}\n"
        f"{rule.parameter}: <b>{history.value:.2f}{unit}</b>\n"
        f"🕒 {when}"
    )


async def send_telegram_message(
    client: httpx.AsyncClient, token: str, chat_id: int, text: str
) -> None:
    """Send one Telegram message; retries up to 3 times on transport/HTTP errors."""
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(MAX_SEND_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(
            (httpx.TransportError, httpx.HTTPStatusError)
        ),
        reraise=True,
    ):
        with attempt:
            response = await client.post(
                url, json=payload, timeout=SEND_TIMEOUT_SECONDS
            )
            response.raise_for_status()


async def _bound_chat_ids(session: AsyncSession) -> list[int]:
    rows = (
        await session.execute(
            select(User.telegram_chat_id).where(
                User.telegram_chat_id.is_not(None)
            )
        )
    ).scalars().all()
    return [int(c) for c in rows if c is not None]


async def notify_alert(
    session: AsyncSession,
    client: httpx.AsyncClient,
    token: str,
    rule: AlertRule,
    history: AlertHistory,
) -> int:
    """Send Telegram notification for one fired alert. Returns chats notified."""
    if not rule.telegram or not token:
        return 0
    location = await session.get(Location, history.location_id)
    name = location.name if location else f"id={history.location_id}"
    text = format_alert_message(rule, history, name)
    chat_ids = await _bound_chat_ids(session)
    if not chat_ids:
        logger.info(
            "alerts.telegram_no_chats",
            rule_id=rule.id,
            history_id=history.id,
        )
        return 0
    sent = 0
    for chat_id in chat_ids:
        try:
            await send_telegram_message(client, token, chat_id, text)
            sent += 1
        except Exception:
            logger.exception(
                "alerts.telegram_send_failed",
                rule_id=rule.id,
                history_id=history.id,
                chat_id=chat_id,
            )
    logger.info(
        "alerts.telegram_sent",
        rule_id=rule.id,
        history_id=history.id,
        sent=sent,
        of=len(chat_ids),
    )
    return sent
