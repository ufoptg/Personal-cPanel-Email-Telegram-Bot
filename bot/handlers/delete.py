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
    assert update.effective_user

    config: Config = context.bot_data["config"]
    store: AccountStore = context.bot_data["store"]
    cpanel: CpanelClient = context.bot_data["cpanel"]

    if not context.args:
        await update.effective_message.reply_text(
            "Usage:\n"
            "• `/delete <email|localpart>`\n"
            "• `/delete *@domain.com` (deletes all under domain/subdomain)\n\n"
            "Removes mailbox(es) from cPanel and from this bot's list."
        )
        return

    target = context.args[0].strip()
    user_id = update.effective_user.id

    # Handle wildcard domain/subdomain bulk deletion (*@domain.com)
    if target.startswith("*@"):
        target_domain = target[2:].strip().lower()
        if not target_domain:
            await update.effective_message.reply_text("Invalid format. Usage: /delete *@domain.com")
            return

        # Fetch tracked accounts (adjust store method if your AccountStore uses a different method name)
        all_accounts = await store.get_all() if hasattr(store, "get_all") else []
        
        # Filter matching accounts for the domain or its subdomains, restricted to the user if applicable
        matching_accounts = [
            acc for acc in all_accounts
            if (acc.domain.lower() == target_domain or acc.domain.lower().endswith(f".{target_domain}"))
            and (not hasattr(acc, "user_id") or acc.user_id == user_id)
        ]

        if not matching_accounts:
            await update.effective_message.reply_text(
                f"No mailboxes found matching domain or subdomain: *@{target_domain}"
            )
            return

        await update.effective_message.reply_text(
            f"Found {len(matching_accounts)} mailbox(es) under *@{target_domain}. Deleting…"
        )

        deleted_count = 0
        failed_count = 0

        for account in matching_accounts:
            address = account.address
            try:
                await cpanel.del_pop(localpart=account.localpart, domain=account.domain)
                await store.delete(account.localpart, account.domain)
                deleted_count += 1
            except Exception as exc:
                logger.exception("Failed to delete %s during bulk delete", address)
                failed_count += 1

        await update.effective_message.reply_text(
            f"Bulk deletion complete for *@{target_domain}:\n"
            f"✅ Successfully deleted: {deleted_count}\n"
            f"❌ Failed: {failed_count}"
        )
        return

    # Existing single account deletion logic
    domain = config.domain_for(user_id)
    localpart = resolve_localpart(target, domain, config.known_domains)
    if not localpart:
        await update.effective_message.reply_text("Invalid address or wrong domain.")
        return

    account = await get_tracked_account(
        store, config, target, user_id
    )
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
