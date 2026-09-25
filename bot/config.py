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
    primary_telegram_id: int
    cpanel_host: str
    cpanel_port: int
    cpanel_user: str
    cpanel_api_token: str
    cpanel_verify_ssl: bool
    email_domain: str
    sub_domain_email: str
    imap_host: str
    imap_port: int
    fernet_key: str
    db_path: Path

    @property
    def cpanel_base_url(self) -> str:
        return f"https://{self.cpanel_host}:{self.cpanel_port}"

    @property
    def known_domains(self) -> frozenset[str]:
        return frozenset({self.email_domain, self.sub_domain_email})

    def domain_for(self, telegram_user_id: int) -> str:
        """Primary user gets EMAIL_DOMAIN; everyone else gets SUB_DOMAIN_EMAIL."""
        if telegram_user_id == self.primary_telegram_id:
            return self.email_domain
        return self.sub_domain_email


def load_config(env_file: str | None = None) -> Config:
    load_dotenv(env_file)

    ids_raw = _require("ALLOWED_TELEGRAM_IDS")
    try:
        id_list = [int(part.strip()) for part in ids_raw.split(",") if part.strip()]
    except ValueError as exc:
        raise RuntimeError("ALLOWED_TELEGRAM_IDS must be comma-separated integers") from exc
    if not id_list:
        raise RuntimeError("ALLOWED_TELEGRAM_IDS must include at least one user ID")

    email_domain = _require("EMAIL_DOMAIN").lower()
    sub_domain_email = _require("SUB_DOMAIN_EMAIL").lower()
    if email_domain == sub_domain_email:
        raise RuntimeError("EMAIL_DOMAIN and SUB_DOMAIN_EMAIL must be different")

    db_path = Path(os.getenv("DB_PATH", "./data/bot.db")).expanduser()
    return Config(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        allowed_telegram_ids=frozenset(id_list),
        primary_telegram_id=id_list[0],
        cpanel_host=_require("CPANEL_HOST"),
        cpanel_port=int(os.getenv("CPANEL_PORT", "2083")),
        cpanel_user=_require("CPANEL_USER"),
        cpanel_api_token=_require("CPANEL_API_TOKEN"),
        cpanel_verify_ssl=_bool("CPANEL_VERIFY_SSL", True),
        email_domain=email_domain,
        sub_domain_email=sub_domain_email,
        imap_host=_require("IMAP_HOST"),
        imap_port=int(os.getenv("IMAP_PORT", "993")),
        fernet_key=_require("FERNET_KEY"),
        db_path=db_path,
    )
