""" /create handler """

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.config import Config
from bot.cpanel import CpanelClient, CpanelError
from bot.crypto import PasswordCrypto
from bot.db import AccountStore
from bot.handlers.common import generate_password, validate_localpart

logger = logging.getLogger(__name__)


@require_auth
async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message
    assert update.effective_user

    config: Config = context.bot_data["config"]
    store: AccountStore = context.bot_data["store"]
    crypto: PasswordCrypto = context.bot_data["crypto"]
    cpanel: CpanelClient = context.bot_data["cpanel"]

    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /create <localpart> [password]\n"
            f"Creates localpart@{config.email_domain}"
        )
        return

    localpart = validate_localpart(context.args[0])
    if not localpart:
        await update.effective_message.reply_text(
            "Invalid localpart. Use letters, numbers, and . _ + - (no leading/trailing dots)."
        )
        return

    existing = await store.get_by_local_or_address(localpart, config.email_domain)
    if existing:
        await update.effective_message.reply_text(
            f"{existing.address} is already tracked by this bot."
        )
        return

    password_provided = len(context.args) >= 2
    password = context.args[1] if password_provided else generate_password()
    if len(password) < 8:
        await update.effective_message.reply_text("Password must be at least 8 characters.")
        return

    address = f"{localpart}@{config.email_domain}"
    await update.effective_message.reply_text(f"Creating {address}…")

    try:
        await cpanel.add_pop(
            localpart=localpart,
            password=password,
            domain=config.email_domain,
        )
    except CpanelError as exc:
        logger.warning("cPanel add_pop failed for %s: %s", address, exc)
        await update.effective_message.reply_text(f"cPanel error: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error creating %s", address)
        await update.effective_message.reply_text(f"Failed to create mailbox: {exc}")
        return

    try:
        password_enc = crypto.encrypt(password)
        await store.add(
            localpart=localpart,
            domain=config.email_domain,
            password_enc=password_enc,
            telegram_user_id=update.effective_user.id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Mailbox created on cPanel but local save failed for %s", address)
        await update.effective_message.reply_text(
            f"Mailbox created on cPanel, but saving locally failed: {exc}\n"
            "Fix the bot DB, then you may need to delete the address in cPanel manually."
        )
        return

    note = "Password was generated for you." if not password_provided else "Using the password you provided."
    await update.effective_message.reply_text(
        f"Created {address}\n"
        f"{note}\n"
        f"Password: {password}\n"
        "Save it now — it won't be shown again."
    )
