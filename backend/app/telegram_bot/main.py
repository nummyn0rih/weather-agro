"""Telegram bot entry point.

Runs as a separate Docker service (see ``docker-compose.yml``). Wires
python-telegram-bot's ``Application`` to the pure handlers in
:mod:`app.telegram_bot.handlers`, opening one DB session per update.
"""

from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable, Sequence

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import async_session_factory
from app.telegram_bot import handlers

log = structlog.get_logger(__name__)

HandlerFn = Callable[..., Awaitable[str]]


def _make_command(
    name: str,
    handler: HandlerFn,
    session_factory: async_sessionmaker,
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]:
    async def _wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.message is None or update.effective_chat is None:
            return
        chat_id = update.effective_chat.id
        args: Sequence[str] = context.args or []
        try:
            async with session_factory() as session:
                text = await handler(session, chat_id, args)
        except Exception:
            log.exception("telegram.handler_failed", command=name, chat_id=chat_id)
            text = "⚠️ Внутренняя ошибка. Попробуй позже."
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)

    return _wrapper


def build_application(token: str) -> Application:
    """Build the ``Application`` with all command handlers registered."""
    app = Application.builder().token(token).build()

    commands: list[tuple[str, HandlerFn]] = [
        ("start", handlers.handle_start),
        ("help", handlers.handle_help),
        ("locations", handlers.handle_locations),
        ("weather", handlers.handle_weather),
        ("forecast", handlers.handle_forecast),
        ("alerts", handlers.handle_alerts),
        ("alerts_history", handlers.handle_alerts_history),
        ("stats", handlers.handle_stats),
    ]
    for name, fn in commands:
        app.add_handler(
            CommandHandler(name, _make_command(name, fn, async_session_factory))
        )
    return app


def run() -> None:
    configure_logging()
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        log.error("telegram.token_missing")
        sys.exit("TELEGRAM_BOT_TOKEN is not set")
    log.info("telegram.bot_starting")
    app = build_application(settings.TELEGRAM_BOT_TOKEN)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    run()
