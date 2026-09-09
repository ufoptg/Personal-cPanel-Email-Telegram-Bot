""" /inbox handler """

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.config import Config
from bot.crypto import PasswordCrypto
from bot.db import AccountStore
from bot.handlers.common import get_tracked_account
from bot.imap_mail import ImapClient, ImapError

logger = logging.getLogger(__name__)


@require_auth
async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message

    config: Config = context.bot_data["config"]
    store: AccountStore = context.bot_data["store"]
    crypto: PasswordCrypto = context.bot_data["crypto"]
    imap: ImapClient = context.bot_data["imap"]

    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /inbox <email|localpart> [n]\n"
            "n = number of recent messages (default 10, max 50)"
        )
        return

    account = await get_tracked_account(store, config, context.args[0])
    if not account:
        await update.effective_message.reply_text(
            "Unknown address. Only bot-created addresses can be checked. Use /list."
        )
        return

    limit = 10
    if len(context.args) >= 2:
        try:
            limit = int(context.args[1])
        except ValueError:
            await update.effective_message.reply_text("n must be an integer.")
            return

    password = crypto.decrypt(account.password_enc)
    try:
        messages = await asyncio.to_thread(
            imap.list_recent, account.address, password, limit
        )
    except ImapError as exc:
        logger.warning("IMAP list failed for %s: %s", account.address, exc)
        await update.effective_message.reply_text(f"IMAP error: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected IMAP error for %s", account.address)
        await update.effective_message.reply_text(f"Failed to read inbox: {exc}")
        return

    if not messages:
        await update.effective_message.reply_text(f"{account.address}: inbox is empty.")
        return

    lines = [f"Inbox for {account.address} (newest first):"]
    for msg in messages:
        lines.append(
            f"• uid {msg.uid} | {msg.date}\n"
            f"  From: {msg.from_}\n"
            f"  Subject: {msg.subject}"
        )
    lines.append("\nRead with: /read " + account.localpart + " <uid>")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n…(truncated)"
    await update.effective_message.reply_text(text)
