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
2. `ALLOWED_TELEGRAM_IDS` — your numeric Telegram user ID (e.g. from `@userinfobot`)
3. cPanel host, user, and API token (cPanel → Security → API Tokens)
4. `EMAIL_DOMAIN`, `IMAP_HOST` (often `mail.yourdomain.com`)
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
| `/create <localpart> [password]` | Create `localpart@EMAIL_DOMAIN` |
| `/list` | List bot-created addresses |
| `/inbox <email\|localpart> [n]` | Recent messages |
| `/read <email\|localpart> <uid>` | Read a message |
| `/delete <email\|localpart>` | Delete from cPanel and bot |
