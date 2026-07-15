# acim-bot

A Course in Miracles bot for **Discord** and **Telegram**.

Look up the title of any of the 365 ACIM Workbook lessons by number.

> **Note:** This bot returns lesson **titles** only, not the full lesson text.
> The full Workbook text is under copyright by the Foundation for Inner Peace.

---

## Features

- 📖 `/acim <1–365>` slash command (Discord) or `/acim <1–365>` command (Telegram)
- Returns the title of the requested lesson
- Discord responses use markdown escaping to prevent formatting/ping issues
- Telegram includes `/start` and `/help` commands for discoverability
- Docker-ready with health checks and graceful shutdown
- Startup validation of lesson data catches corruption immediately

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
3. Copy the bot token into `.env` as `DISCORD_TOKEN`
4. Invite the bot to your server with the `applications.commands` scope

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
pip install .

# Set environment variables, then:
python bot.py
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_MODE` | No | `discord` | Must be `discord` or `telegram` |
| `DISCORD_TOKEN` | Yes\* | — | Discord bot token |
| `TELEGRAM_TOKEN` | Yes\* | — | Telegram bot token |
| `HEALTH_PORT` | No | `8080` | HTTP port for health checks (1–65535) |
| `DISCORD_GUILD_ID` | No | — | Restrict command sync to one guild (dev only) |
| `DISCORD_SYNC_COMMANDS` | No | `true` | Set `false` to skip command sync on startup |

\* Only the token for the active `BOT_MODE` is required.

---

## CI

The repo includes a `tests/` directory with smoke tests. To run them locally:

```bash
pip install ".[dev]"
BOT_MODE=discord DISCORD_TOKEN=test pytest -q
```

To add a GitHub Actions CI workflow, create `.github/workflows/ci.yml` — this
repo's GitHub App permissions don't allow pushing workflow files automatically.

## Architecture

```
acim-bot/
├── bot.py                 # Main application (Discord + Telegram)
├── data/
│   └── lessons.json       # All 365 lesson titles
├── tests/
│   └── test_bot.py        # Smoke tests
├── Dockerfile             # Multi-stage build, health check, non-root user
├── docker-compose.yml     # Health check + graceful stop
├── Makefile               # build/up/down/logs/health/restart/clean
├── pyproject.toml         # Single source of truth for dependencies
├── .env.example           # Documented env vars
├── .gitignore
├── .dockerignore
└── LICENSE                # MIT
```

---

## License

MIT
