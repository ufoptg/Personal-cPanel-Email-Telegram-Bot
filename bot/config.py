"""Load and validate environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    allowed_telegram_ids: frozenset[int]
    cpanel_host: str
    cpanel_port: int
    cpanel_user: str
    cpanel_api_token: str
    cpanel_verify_ssl: bool
    email_domain: str
    imap_host: str
    imap_port: int
    fernet_key: str
    db_path: Path

    @property
    def cpanel_base_url(self) -> str:
        return f"https://{self.cpanel_host}:{self.cpanel_port}"


def load_config(env_file: str | None = None) -> Config:
    load_dotenv(env_file)

    ids_raw = _require("ALLOWED_TELEGRAM_IDS")
    try:
        allowed = frozenset(int(part.strip()) for part in ids_raw.split(",") if part.strip())
    except ValueError as exc:
        raise RuntimeError("ALLOWED_TELEGRAM_IDS must be comma-separated integers") from exc
    if not allowed:
        raise RuntimeError("ALLOWED_TELEGRAM_IDS must include at least one user ID")

    db_path = Path(os.getenv("DB_PATH", "./data/bot.db")).expanduser()
    return Config(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        allowed_telegram_ids=allowed,
        cpanel_host=_require("CPANEL_HOST"),
        cpanel_port=int(os.getenv("CPANEL_PORT", "2083")),
        cpanel_user=_require("CPANEL_USER"),
        cpanel_api_token=_require("CPANEL_API_TOKEN"),
        cpanel_verify_ssl=_bool("CPANEL_VERIFY_SSL", True),
        email_domain=_require("EMAIL_DOMAIN").lower(),
        imap_host=_require("IMAP_HOST"),
        imap_port=int(os.getenv("IMAP_PORT", "993")),
        fernet_key=_require("FERNET_KEY"),
        db_path=db_path,
    )
