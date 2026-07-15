# acim-bot

A Course in Miracles bot for **Discord** and **Telegram**.

Look up the title of any of the 365 ACIM Workbook lessons by number, get a random lesson, or search by keyword.

> **Note:** This bot returns lesson **titles** only, not the full lesson text.
> The full Workbook text is under copyright by the Foundation for Inner Peace.

---

## Features

- 📖 `/acim lesson <1-365>` — look up a lesson by number (Discord)
- 🎲 `/acim random` — get a random lesson (Discord)
- 🔍 `/acim search <keyword>` — search lesson titles by keyword (Discord)
- 📖 `/acim <1-365>` — look up by number (Telegram)
- 🎲 `/acim random` — random lesson (Telegram)
- 🔍 `/acimsearch <keyword>` — search lesson titles by keyword (Telegram)
- Discord responses use markdown escaping to prevent formatting/ping issues
- Telegram includes `/start` and `/help` commands for discoverability
- Search result limit is configurable via `ACIM_SEARCH_MAX_RESULTS`
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
| `HEALTH_PORT` | No | `8080` | HTTP port for health checks (1-65535) |
| `ACIM_SEARCH_MAX_RESULTS` | No | `3` | Max search results returned (1-25) |
| `DISCORD_GUILD_ID` | No | — | Restrict command sync to one guild (dev only) |
| `DISCORD_SYNC_COMMANDS` | No | `true` | Set `false` to skip command sync on startup |

\* Only the token for the active `BOT_MODE` is required.

---

## Example Usage

### Discord

```
/acim lesson number: 48     →  📖 Lesson 48
                               There is nothing to fear.

/acim random                →  🎲 Lesson 217
                               ...

/acim search query: fear    →  🔍 Results for "fear":
                               📖 Lesson 48: There is nothing to fear.
                               📖 Lesson 240: Fear is not justified...
                               📖 Lesson 293: All fear is past...
```

### Telegram

```
/acim 48                    →  📖 Lesson 48
                               There is nothing to fear.

/acim random                →  🎲 Lesson 217
                               ...

/acimsearch fear            →  🔍 Results for "fear": ...
```

---

## Architecture

```
acim-bot/
├── bot.py                 # Main application (Discord + Telegram)
├── data/
│   └── lessons.json       # All 365 lesson titles
├── tests/
│   └── test_bot.py        # Smoke + search + random tests
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

## CI

The repo includes a `tests/` directory with smoke tests. To run them locally:

```bash
pip install ".[dev]"
BOT_MODE=discord DISCORD_TOKEN=test pytest -q
```

To add a GitHub Actions CI workflow, create `.github/workflows/ci.yml` — this
repo's GitHub App permissions don't allow pushing workflow files automatically.

---

## License

MIT
