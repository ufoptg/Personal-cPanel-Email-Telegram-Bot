""" /start handler """

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import require_auth


HELP_TEXT = """Personal cPanel email bot.

Commands:
/create <localpart> [password] — create an address
/list — list addresses created via this bot
/inbox <email|localpart> [n] — recent inbox messages
/read <email|localpart> <uid> — read a message
/delete <email|localpart> — delete address from cPanel and bot

You are authorized."""


@require_auth
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message
    await update.effective_message.reply_text(HELP_TEXT)
