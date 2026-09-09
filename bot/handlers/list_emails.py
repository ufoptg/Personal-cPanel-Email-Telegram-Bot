""" /list handler """

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.db import AccountStore


@require_auth
async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message
    store: AccountStore = context.bot_data["store"]
    accounts = await store.list_all()
    if not accounts:
        await update.effective_message.reply_text(
            "No addresses created via this bot yet. Use /create <localpart>"
        )
        return

    lines = [f"• {account.address} (created {account.created_at})" for account in accounts]
    text = "Bot-created addresses:\n" + "\n".join(lines)
    await update.effective_message.reply_text(text)
