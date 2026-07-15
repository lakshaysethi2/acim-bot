# acim-bot

A Course in Miracles bot for **Discord** and **Telegram**.

Look up any of the 365 ACIM Workbook lessons by number.

---

## Features

- 📖 `/acim <1–365>` slash command (Discord) or `/acim <1–365>` command (Telegram)
- Returns the title of the requested lesson
- Docker-ready with health checks and graceful shutdown
- Single JSON data file — easy to update

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/lakshaysethi2/acim-bot.git
cd acim-bot
cp .env.example .env
# Edit .env with your bot token(s)
```

### 2. Discord setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application → Bot
3. Enable **Message Content Intent** (not needed for this bot, but fine to leave on)
4. Copy the bot token into `.env` as `DISCORD_TOKEN`
5. Invite the bot to your server with the `applications.commands` scope

### 3. Telegram setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Create a new bot and copy the token into `.env` as `TELEGRAM_TOKEN`
3. Set `BOT_MODE=telegram` in `.env`

---

## Running

### Docker (recommended)

```bash
make build
make up
make logs        # tail logs
make health      # check health status
make down        # stop
```

### Local (Python)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# For Telegram, also install:
pip install python-telegram-bot

# Set environment variables, then:
python bot.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_MODE` | No | `discord` | `discord` or `telegram` |
| `DISCORD_TOKEN` | Yes* | — | Discord bot token |
| `TELEGRAM_TOKEN` | Yes* | — | Telegram bot token |
| `HEALTH_PORT` | No | `8080` | HTTP port for health checks |
| `DISCORD_GUILD_ID` | No | — | Restrict command sync to one guild (dev) |

\* Only the token for the active `BOT_MODE` is required.

---

## Architecture

```
acim-bot/
├── bot.py                # Main application (Discord + Telegram)
├── data/
│   └── lessons.json      # All 365 lesson titles
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── .dockerignore
```

---

## License

MIT
