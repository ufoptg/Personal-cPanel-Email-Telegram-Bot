# Personal cPanel Email Telegram Bot

Python Telegram bot that creates cPanel email accounts, tracks ones created via the bot, and reads those inboxes over IMAP.

## Setup

```bash
cd /home/droid/tgbot
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env
```

(If you prefer plain venv: `python3 -m venv .venv` then `pip install -r requirements.txt`.)

Edit `.env`:

1. `TELEGRAM_BOT_TOKEN` from [@BotFather](https://t.me/BotFather)
2. `ALLOWED_TELEGRAM_IDS` — comma-separated Telegram user IDs (e.g. from `@userinfobot`). The **first** ID is primary and uses `EMAIL_DOMAIN`; any other allowed ID uses `SUB_DOMAIN_EMAIL`
3. cPanel host, user, and API token (cPanel → Security → API Tokens)
4. `EMAIL_DOMAIN`, `SUB_DOMAIN_EMAIL`, `IMAP_HOST` (often `mail.yourdomain.com`)
5. Generate `FERNET_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

From the bot host, ensure outbound access to cPanel `:2083` and IMAP `:993`.

## Run

```bash
source .venv/bin/activate
python -m bot.main
```

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Help |
| `/create <localpart> [password]` | Create address on your domain (`EMAIL_DOMAIN` for primary ID, else `SUB_DOMAIN_EMAIL`) |
| `/list` | List bot-created addresses |
| `/inbox <email\|localpart> [n]` | Recent inbox messages |
| `/spam <email\|localpart> [n]` | Recent spam/junk messages |
| `/read <email\|localpart> <uid> [spam]` | Read a message (`spam` for spam-folder UIDs) |
| `/delete <email\|localpart>` | Delete from cPanel and bot |
