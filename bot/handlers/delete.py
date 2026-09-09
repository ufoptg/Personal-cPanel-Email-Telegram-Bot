""" /delete handler """

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.auth import require_auth
from bot.config import Config
from bot.cpanel import CpanelClient, CpanelError
from bot.db import AccountStore
from bot.handlers.common import get_tracked_account, resolve_localpart

logger = logging.getLogger(__name__)


@require_auth
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_message

    config: Config = context.bot_data["config"]
    store: AccountStore = context.bot_data["store"]
    cpanel: CpanelClient = context.bot_data["cpanel"]

    if not context.args:
        await update.effective_message.reply_text(
            "Usage: /delete <email|localpart>\n"
            "Removes the mailbox from cPanel and from this bot's list."
        )
        return

    localpart = resolve_localpart(context.args[0], config.email_domain)
    if not localpart:
        await update.effective_message.reply_text("Invalid address or wrong domain.")
        return

    account = await get_tracked_account(store, config, localpart)
    if not account:
        await update.effective_message.reply_text(
            "Unknown address. Only bot-created addresses can be deleted here. Use /list."
        )
        return

    address = account.address
    await update.effective_message.reply_text(f"Deleting {address}…")

    try:
        await cpanel.del_pop(localpart=account.localpart, domain=account.domain)
    except CpanelError as exc:
        logger.warning("cPanel del_pop failed for %s: %s", address, exc)
        await update.effective_message.reply_text(
            f"cPanel error: {exc}\nLocal record was not removed."
        )
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error deleting %s", address)
        await update.effective_message.reply_text(f"Failed to delete mailbox: {exc}")
        return

    removed = await store.delete(account.localpart, account.domain)
    if removed:
        await update.effective_message.reply_text(f"Deleted {address} from cPanel and bot.")
    else:
        await update.effective_message.reply_text(
            f"Deleted {address} from cPanel, but local record was already gone."
        )
