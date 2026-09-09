"""Telegram bot entrypoint — long polling."""

from __future__ import annotations

import logging
import sys

from telegram.ext import Application, CommandHandler

from bot.config import load_config
from bot.cpanel import CpanelClient
from bot.crypto import PasswordCrypto
from bot.db import AccountStore
from bot.handlers.create import create_command
from bot.handlers.delete import delete_command
from bot.handlers.inbox import inbox_command
from bot.handlers.list_emails import list_command
from bot.handlers.read import read_command
from bot.handlers.start import start_command
from bot.imap_mail import ImapClient

logging.basicConfig(
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    store: AccountStore = application.bot_data["store"]
    await store.init()
    logger.info("Database ready at %s", application.bot_data["config"].db_path)


def main() -> None:
    try:
        config = load_config()
    except RuntimeError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    store = AccountStore(config.db_path)
    crypto = PasswordCrypto(config.fernet_key)
    cpanel = CpanelClient(config)
    imap = ImapClient(config)

    application = (
        Application.builder()
        .token(config.telegram_bot_token)
        .post_init(post_init)
        .build()
    )
    application.bot_data["config"] = config
    application.bot_data["store"] = store
    application.bot_data["crypto"] = crypto
    application.bot_data["cpanel"] = cpanel
    application.bot_data["imap"] = imap

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", start_command))
    application.add_handler(CommandHandler("create", create_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("inbox", inbox_command))
    application.add_handler(CommandHandler("read", read_command))
    application.add_handler(CommandHandler("delete", delete_command))

    logger.info(
        "Starting bot (domain=%s, allowed_users=%s)",
        config.email_domain,
        sorted(config.allowed_telegram_ids),
    )
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
