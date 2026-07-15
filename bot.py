"""
A Course in Miracles (ACIM) Bot — Discord & Telegram

Responds with the title of any of the 365 ACIM Workbook lessons.
"""

import json
import logging
import os
import signal
import sys
from pathlib import Path

import aiohttp.web
import discord
from discord import app_commands
from discord.ext import commands

# ---------------------------------------------------------------------------
# Logging — quiet root; explicit levels for our own code + libraries we care about
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("acim-bot").setLevel(logging.INFO)
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
log = logging.getLogger("acim-bot")

# ---------------------------------------------------------------------------
# Configuration — validated at startup
# ---------------------------------------------------------------------------
VALID_MODES = {"discord", "telegram"}


def _env_int(key: str, default: int, *, min_val: int = 1, max_val: int = 65535) -> int:
    """Read an integer env var with safe fallback on bad values."""
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (ValueError, TypeError):
        log.warning("Invalid value for %s=%r, using default %d", key, raw, default)
        return default
    if not (min_val <= value <= max_val):
        log.warning("Value for %s=%d out of range [%d, %d], using default %d",
                     key, value, min_val, max_val, default)
        return default
    return value


HEALTH_PORT: int = _env_int("HEALTH_PORT", 8080)

BOT_MODE: str = os.getenv("BOT_MODE", "discord").strip().lower()
if BOT_MODE not in VALID_MODES:
    log.error("BOT_MODE must be 'discord' or 'telegram', got %r", BOT_MODE)
    sys.exit(1)

DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID: str = os.getenv("DISCORD_GUILD_ID", "")
DISCORD_SYNC_COMMANDS: bool = os.getenv("DISCORD_SYNC_COMMANDS", "true").strip().lower() in {"true", "1", "yes"}

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

# ---------------------------------------------------------------------------
# Lesson data
# ---------------------------------------------------------------------------
LESSONS_PATH = Path(__file__).resolve().parent / "data" / "lessons.json"

_lessons: dict[str, str] | None = None


def load_lessons() -> dict[str, str]:
    """Load and validate lesson data. Cached after first call."""
    global _lessons
    if _lessons is not None:
        return _lessons

    if not LESSONS_PATH.exists():
        log.error("Lessons file not found: %s", LESSONS_PATH)
        sys.exit(1)

    with LESSONS_PATH.open(encoding="utf-8") as f:
        _lessons = json.load(f)

    # Startup validation — catches corrupted / incomplete data immediately
    if len(_lessons) != 365:
        log.error("Expected 365 lessons, got %d", len(_lessons))
        sys.exit(1)
    for i in range(1, 366):
        if str(i) not in _lessons:
            log.error("Missing lesson %d in %s", i, LESSONS_PATH)
            sys.exit(1)
        if not _lessons[str(i)].strip():
            log.error("Empty title for lesson %d in %s", i, LESSONS_PATH)
            sys.exit(1)

    log.info("Loaded and validated %d lessons from %s", len(_lessons), LESSONS_PATH)
    return _lessons


def get_lesson(number: int) -> str | None:
    """Return the title for a lesson number (1–365), or None."""
    return load_lessons().get(str(number))


# ---------------------------------------------------------------------------
# Health-check server (used by Docker HEALTHCHECK)
# ---------------------------------------------------------------------------
_health_runner: aiohttp.web.AppRunner | None = None


async def start_health_server() -> None:
    """Start the health-check HTTP server (idempotent)."""
    global _health_runner
    if _health_runner is not None:
        return

    async def handle(_request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(text="ok")

    app = aiohttp.web.Application()
    app.router.add_get("/health", handle)
    _health_runner = aiohttp.web.AppRunner(app)
    await _health_runner.setup()
    site = aiohttp.web.TCPSite(_health_runner, "0.0.0.0", HEALTH_PORT)
    await site.start()
    log.info("Health-check server listening on port %d", HEALTH_PORT)


# ---------------------------------------------------------------------------
# Discord bot
# ---------------------------------------------------------------------------
_discord_started: bool = False


def _build_discord_bot() -> commands.Bot:
    """Create and configure the Discord bot."""
    intents = discord.Intents.default()
    bot = commands.Bot(intents=intents)

    @bot.event
    async def on_ready() -> None:
        global _discord_started
        if _discord_started:
            return
        _discord_started = True

        log.info("Discord bot logged in as %s (id=%s)", bot.user, bot.user.id)
        await start_health_server()

        if DISCORD_SYNC_COMMANDS:
            try:
                if DISCORD_GUILD_ID:
                    guild = discord.Object(id=int(DISCORD_GUILD_ID))
                    synced = await bot.tree.sync(guild=guild)
                    log.info("Synced %d command(s) to guild %s", len(synced), DISCORD_GUILD_ID)
                else:
                    synced = await bot.tree.sync()
                    log.info("Synced %d global command(s)", len(synced))
            except Exception:
                log.exception("Failed to sync application commands")
        else:
            log.info("Command sync skipped (DISCORD_SYNC_COMMANDS=false)")

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
        safe_title = discord.utils.escape_markdown(
            discord.utils.escape_mentions(title)
        )
        await interaction.response.send_message(
            f"📖 **Lesson {lesson}**\n{safe_title}"
        )

    return bot


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------
def _run_telegram_bot() -> None:
    """Start the Telegram bot (blocking)."""
    try:
        from telegram import Update
        from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
    except ImportError:
        log.error(
            "python-telegram-bot is not installed. "
            "Install it with: pip install python-telegram-bot"
        )
        sys.exit(1)

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def post_init(application: object) -> None:
        """Hook that runs after the Telegram app initializes — start health server here."""
        await start_health_server()

    app.post_init = post_init  # type: ignore[assignment]

    TELEGRAM_HELP_TEXT = (
        "📖 *A Course in Miracles Bot*\n\n"
        "Use /acim <1–365> to look up a lesson title.\n"
        "Example: /acim 1"
    )

    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(TELEGRAM_HELP_TEXT)  # type: ignore[union-attr]

    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(TELEGRAM_HELP_TEXT)  # type: ignore[union-attr]

    async def acim_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.effective_message.reply_text(  # type: ignore[union-attr]
                "Usage: /acim <lesson number 1–365>"
            )
            return
        try:
            lesson = int(context.args[0])
        except ValueError:
            await update.effective_message.reply_text("⚠️ Please provide a valid number.")  # type: ignore[union-attr]
            return
        if lesson < 1 or lesson > 365:
            await update.effective_message.reply_text(  # type: ignore[union-attr]
                "⚠️ Lesson number must be between 1 and 365."
            )
            return
        title = get_lesson(lesson)
        if title is None:
            await update.effective_message.reply_text("⚠️ Could not find that lesson.")  # type: ignore[union-attr]
            return
        await update.effective_message.reply_text(f"📖 Lesson {lesson}\n{title}")  # type: ignore[union-attr]

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("acim", acim_command))

    log.info("Starting Telegram bot…")
    app.run_polling()


# ---------------------------------------------------------------------------
# Signal handling & graceful shutdown
# ---------------------------------------------------------------------------
def _handle_signal(signum: int, _frame: object) -> None:
    sig_name = signal.Signals(signum).name
    log.info("Received %s — shutting down gracefully…", sig_name)
    raise SystemExit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Validate required tokens for the selected mode
    if BOT_MODE == "telegram":
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
