"""Authorization helpers for personal-only bot access."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import Config

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[Any]]
F = TypeVar("F", bound=Handler)


def is_allowed(update: Update, config: Config) -> bool:
    user = update.effective_user
    return bool(user and user.id in config.allowed_telegram_ids)


def require_auth(handler: F) -> F:
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Any:
        config: Config = context.bot_data["config"]
        if not is_allowed(update, config):
            if update.effective_message:
                await update.effective_message.reply_text("Unauthorized.")
            return None
        return await handler(update, context)

    return wrapper  # type: ignore[return-value]
