"""
A Course in Miracles (ACIM) Bot — Discord & Telegram

Responds with the title of any of the 365 ACIM Workbook lessons.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("acim-bot")

# ---------------------------------------------------------------------------
# Lesson data
# ---------------------------------------------------------------------------
LESSONS_PATH = Path(__file__).resolve().parent / "data" / "lessons.json"

_lessons: dict[str, str] = {}


def load_lessons() -> dict[str, str]:
    """Load lesson data from the JSON file. Cached after first call."""
    global _lessons  # noqa: PLW0603
    if not _lessons:
        if not LESSONS_PATH.exists():
            log.error("Lessons file not found: %s", LESSONS_PATH)
            sys.exit(1)
        with LESSONS_PATH.open(encoding="utf-8") as f:
            _lessons = json.load(f)
        log.info("Loaded %d lessons from %s", len(_lessons), LESSONS_PATH)
    return _lessons


def get_lesson(number: int) -> str | None:
    """Return the title for a lesson number (1–365), or None."""
    return load_lessons().get(str(number))


# ---------------------------------------------------------------------------
# Health-check helper (used by Docker HEALTHCHECK)
# ---------------------------------------------------------------------------
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))


async def _health_server() -> None:
    """Tiny aiohttp server that answers GET /health with 200."""
    from aiohttp import web  # imported lazily so it's not required at import time

    async def handle(_request: web.Request) -> web.Response:
        return web.Response(text="ok")

    app = web.Application()
    app.router.add_get("/health", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HEALTH_PORT)
    await site.start()
    log.info("Health-check server listening on port %d", HEALTH_PORT)


# ---------------------------------------------------------------------------
# Discord bot
# ---------------------------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")


def _build_discord_bot() -> commands.Bot:
    """Create and configure the Discord bot."""
    intents = discord.Intents.default()
    bot = commands.Bot(intents=intents)

    @bot.event
    async def on_ready() -> None:
        log.info("Discord bot logged in as %s (id=%s)", bot.user, bot.user.id)
        await _health_server()
        try:
            synced = await bot.tree.sync()
            log.info("Synced %d application command(s)", len(synced))
        except Exception:
            log.exception("Failed to sync application commands")

    @bot.tree.command(
        name="acim",
        description="Look up an ACIM Workbook lesson by number (1–365)",
    )
    @app_commands.describe(lesson="Lesson number (1–365)")
    async def acim(interaction: discord.Interaction, lesson: int) -> None:
        if lesson < 1 or lesson > 365:
            await interaction.response.send_message(
                "⚠️ Lesson number must be between 1 and 365.", ephemeral=True
            )
            return
        title = get_lesson(lesson)
        if title is None:
            await interaction.response.send_message(
                "⚠️ Could not find that lesson.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"📖 **Lesson {lesson}**\n{title}"
        )

    return bot


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")


def _run_telegram_bot() -> None:
    """Start the Telegram bot (blocking)."""
    import asyncio

    try:
        from telegram import Update
        from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
    except ImportError:
        log.error(
            "python-telegram-bot is not installed. "
            "Install it with: pip install acim-bot[telegram]"
        )
        sys.exit(1)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def acim_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "Usage: /acim <lesson number 1–365>"
            )
            return
        try:
            lesson = int(context.args[0])
        except ValueError:
            await update.message.reply_text("⚠️ Please provide a valid number.")
            return
        if lesson < 1 or lesson > 365:
            await update.message.reply_text(
                "⚠️ Lesson number must be between 1 and 365."
            )
            return
        title = get_lesson(lesson)
        if title is None:
            await update.message.reply_text("⚠️ Could not find that lesson.")
            return
        await update.message.reply_text(f"📖 Lesson {lesson}\n{title}")

    app.add_handler(CommandHandler("acim", acim_command))

    log.info("Starting Telegram bot…")
    app.run_polling()


# ---------------------------------------------------------------------------
# Signal handling & graceful shutdown
# ---------------------------------------------------------------------------
_shutdown = False


def _handle_signal(signum: int, _frame: Any) -> None:
    global _shutdown  # noqa: PLW0603
    sig_name = signal.Signals(signum).name
    log.info("Received %s — shutting down gracefully…", sig_name)
    _shutdown = True
    # Raising SystemExit lets discord.py / telegram cleanup run
    raise SystemExit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    mode = os.getenv("BOT_MODE", "discord").lower()

    if mode == "telegram":
        if not TELEGRAM_TOKEN:
            log.error("TELEGRAM_TOKEN is required for Telegram mode.")
            sys.exit(1)
        _run_telegram_bot()
    else:
        if not DISCORD_TOKEN:
            log.error("DISCORD_TOKEN is required for Discord mode.")
            sys.exit(1)
        bot = _build_discord_bot()
        bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
