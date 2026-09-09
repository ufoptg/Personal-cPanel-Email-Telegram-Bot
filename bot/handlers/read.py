""" /read handler """

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

_TELEGRAM_CHUNK = 3500


@require_auth
async def read_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message

    config: Config = context.bot_data["config"]
    store: AccountStore = context.bot_data["store"]
    crypto: PasswordCrypto = context.bot_data["crypto"]
    imap: ImapClient = context.bot_data["imap"]

    if len(context.args) < 2:
        await update.effective_message.reply_text(
            "Usage: /read <email|localpart> <uid>\n"
            "Get uid from /inbox"
        )
        return

    account = await get_tracked_account(store, config, context.args[0])
    if not account:
        await update.effective_message.reply_text(
            "Unknown address. Only bot-created addresses can be checked. Use /list."
        )
        return

    uid = context.args[1].strip()
    if not uid.isdigit():
        await update.effective_message.reply_text("uid must be a number from /inbox.")
        return

    password = crypto.decrypt(account.password_enc)
    try:
        message = await asyncio.to_thread(
            imap.fetch_message, account.address, password, uid
        )
    except ImapError as exc:
        logger.warning("IMAP read failed for %s uid=%s: %s", account.address, uid, exc)
        await update.effective_message.reply_text(f"IMAP error: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected IMAP read error for %s", account.address)
        await update.effective_message.reply_text(f"Failed to read message: {exc}")
        return

    header = (
        f"From: {message.from_}\n"
        f"Date: {message.date}\n"
        f"Subject: {message.subject}\n"
        f"UID: {message.uid}\n"
        f"{'—' * 16}\n"
    )
    body = message.body
    full = header + body
    if message.truncated and not body.endswith("…(truncated)"):
        full += "\n\n…(truncated)"

    # Split into Telegram-safe chunks without Markdown (bodies may break parsing)
    chunks: list[str] = []
    remaining = full
    while remaining:
        chunks.append(remaining[:_TELEGRAM_CHUNK])
        remaining = remaining[_TELEGRAM_CHUNK:]

    for chunk in chunks:
        await update.effective_message.reply_text(chunk)
