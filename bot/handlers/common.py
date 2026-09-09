"""Shared helpers for command handlers."""

from __future__ import annotations

import re
import secrets
import string

from bot.config import Config
from bot.db import Account, AccountStore

_LOCALPART_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._+-]{0,62}[a-z0-9])?$", re.IGNORECASE)


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_localpart(localpart: str) -> str | None:
    localpart = localpart.strip().lower()
    if not localpart or not _LOCALPART_RE.match(localpart):
        return None
    if ".." in localpart:
        return None
    return localpart


def resolve_localpart(value: str, domain: str) -> str | None:
    value = value.strip().lower()
    if "@" in value:
        local, _, addr_domain = value.partition("@")
        if addr_domain != domain.lower():
            return None
        return validate_localpart(local)
    return validate_localpart(value)


async def get_tracked_account(
    store: AccountStore,
    config: Config,
    value: str,
) -> Account | None:
    return await store.get_by_local_or_address(value, config.email_domain)
