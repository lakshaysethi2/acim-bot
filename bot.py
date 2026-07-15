"""
A Course in Miracles (ACIM) Bot — Discord & Telegram

Responds with the title of any of the 365 ACIM Workbook lessons.
Supports lookup by number, random lesson, and keyword search.
"""

import json
import logging
import os
import random
import signal
import sys
from pathlib import Path

import aiohttp.web
import discord
from discord import app_commands
from discord.ext import commands
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOTAL_LESSONS = 365
VALID_MODES = {"discord", "telegram"}
DEFAULT_SEARCH_MAX = 3

# ---------------------------------------------------------------------------
# Logging — quiet root; explicit levels for our own code + libraries
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
# Configuration — read eagerly but validated in main()
# ---------------------------------------------------------------------------


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
        log.warning(
            "Value for %s=%d out of range [%d, %d], using default %d",
            key, value, min_val, max_val, default,
        )
        return default
    return value


HEALTH_PORT: int = _env_int("HEALTH_PORT", 8080)
ACIM_SEARCH_MAX_RESULTS: int = _env_int(
    "ACIM_SEARCH_MAX_RESULTS", DEFAULT_SEARCH_MAX, min_val=1, max_val=25,
)

BOT_MODE: str = os.getenv("BOT_MODE", "discord").strip().lower()
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
DISCORD_GUILD_ID: str = os.getenv("DISCORD_GUILD_ID", "")
_sync_raw = os.getenv("DISCORD_SYNC_COMMANDS", "true").strip().lower()
DISCORD_SYNC_COMMANDS: bool = _sync_raw in {"true", "1", "yes"}
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")

# ---------------------------------------------------------------------------
# Lesson data
# ---------------------------------------------------------------------------
LESSONS_PATH = Path(__file__).resolve().parent / "data" / "lessons.json"

_lessons: dict[str, str] | None = None


def load_lessons() -> dict[str, str]:
    """Load and validate lesson data. Cached after first call."""
    global _lessons  # noqa: PLW0603
    if _lessons is not None:
        return _lessons

    if not LESSONS_PATH.exists():
        log.error("Lessons file not found: %s", LESSONS_PATH)
        sys.exit(1)

    with LESSONS_PATH.open(encoding="utf-8") as f:
        _lessons = json.load(f)

    # Startup validation — catches corrupted / incomplete data immediately
    if len(_lessons) != TOTAL_LESSONS:
        log.error("Expected %d lessons, got %d", TOTAL_LESSONS, len(_lessons))
        sys.exit(1)
    for i in range(1, TOTAL_LESSONS + 1):
        if str(i) not in _lessons:
            log.error("Missing lesson %d in %s", i, LESSONS_PATH)
            sys.exit(1)
        if not _lessons[str(i)].strip():
            log.error("Empty title for lesson %d in %s", i, LESSONS_PATH)
            sys.exit(1)

    log.info(
        "Loaded and validated %d lessons from %s", len(_lessons), LESSONS_PATH
    )
    return _lessons


def is_valid_lesson(number: int) -> bool:
    """Return True if number is a valid lesson index (1-TOTAL_LESSONS)."""
    return 1 <= number <= TOTAL_LESSONS


def get_lesson(number: int) -> str | None:
    """Return the title for a lesson number (1-365), or None."""
    return load_lessons().get(str(number))


def get_random_lesson() -> tuple[int, str]:
    """Return a random lesson as (number, title)."""
    number = random.randint(1, TOTAL_LESSONS)
    title = get_lesson(number)
    # Validated at load time — title is never empty for 1..TOTAL_LESSONS
    assert title is not None  # noqa: S101
    return number, title


def search_lessons(
    query: str, max_results: int = ACIM_SEARCH_MAX_RESULTS,
) -> list[tuple[int, str]]:
    """Search lesson titles by keyword. Returns up to max_results matches.

    Case-insensitive substring match over the 365 titles, ordered by lesson
    number. Stops once max_results matches are found.
    """
    lessons = load_lessons()
    query_lower = query.lower().strip()
    if not query_lower:
        return []
    results: list[tuple[int, str]] = []
    for key in sorted(lessons, key=int):
        title = lessons[key]
        if query_lower in title.lower():
            results.append((int(key), title))
            if len(results) >= max_results:
                break
    return results


# ---------------------------------------------------------------------------
# Health-check server (used by Docker HEALTHCHECK)
# ---------------------------------------------------------------------------
_health_runner: aiohttp.web.AppRunner | None = None


async def start_health_server() -> None:
    """Start the health-check HTTP server (idempotent)."""
    global _health_runner  # noqa: PLW0603
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
    bot = commands.Bot(command_prefix="!", intents=intents)

    # Slash-command group:
    #   /acim lesson <n> | /acim random | /acim search <query>
    acim_group = app_commands.Group(
        name="acim",
        description="A Course in Miracles Workbook lessons",
    )

    @acim_group.command(
        name="lesson",
        description="Look up an ACIM Workbook lesson by number (1-365)",
    )
    @app_commands.describe(number="Lesson number (1-365)")
    async def lesson(interaction: discord.Interaction, number: int) -> None:
        if not is_valid_lesson(number):
            await interaction.response.send_message(
                f"⚠️ Lesson number must be between 1 and {TOTAL_LESSONS}.",
                ephemeral=True,
            )
            return
        title = get_lesson(number)
        if title is None:
            await interaction.response.send_message(
                "⚠️ Could not find that lesson.", ephemeral=True
            )
            return
        safe_title = discord.utils.escape_markdown(
            discord.utils.escape_mentions(title)
        )
        await interaction.response.send_message(
            f"📖 **Lesson {number}**\n{safe_title}"
        )

    @acim_group.command(
        name="random",
        description="Get a random ACIM Workbook lesson",
    )
    async def random_lesson(interaction: discord.Interaction) -> None:
        number, title = get_random_lesson()
        safe_title = discord.utils.escape_markdown(
            discord.utils.escape_mentions(title)
        )
        await interaction.response.send_message(
            f"🎲 **Lesson {number}**\n{safe_title}"
        )

    @acim_group.command(
        name="search",
        description="Search ACIM lesson titles by keyword",
    )
    @app_commands.describe(query="Keyword to search for in lesson titles")
    async def search(interaction: discord.Interaction, query: str) -> None:
        results = search_lessons(query)
        if not results:
            await interaction.response.send_message(
                f"🔍 No lessons found matching "
                f"**{discord.utils.escape_markdown(query)}**.",
                ephemeral=True,
            )
            return
        lines = [
            f"📖 **Lesson {num}**: "
            f"{discord.utils.escape_markdown(discord.utils.escape_mentions(title))}"
            for num, title in results
        ]
        header = f"🔍 Results for **{discord.utils.escape_markdown(query)}**:"
        await interaction.response.send_message(
            f"{header}\n" + "\n".join(lines)
        )

    bot.tree.add_command(acim_group)

    @bot.event
    async def on_ready() -> None:
        global _discord_started  # noqa: PLW0603
        if _discord_started:
            return
        _discord_started = True

        if bot.user is None:
            log.error("on_ready fired but bot.user is None")
            return
        log.info("Discord bot logged in as %s (id=%s)", bot.user, bot.user.id)
        await start_health_server()

        log.info("DISCORD_SYNC_COMMANDS=%s", DISCORD_SYNC_COMMANDS)
        if DISCORD_SYNC_COMMANDS:
            try:
                if DISCORD_GUILD_ID:
                    try:
                        guild_id = int(DISCORD_GUILD_ID)
                    except ValueError:
                        log.error(
                            "DISCORD_GUILD_ID is not a valid integer: %r",
                            DISCORD_GUILD_ID,
                        )
                        return
                    guild = discord.Object(id=guild_id)
                    synced = await bot.tree.sync(guild=guild)
                    log.info(
                        "Synced %d command(s) to guild %s",
                        len(synced), DISCORD_GUILD_ID,
                    )
                else:
                    synced = await bot.tree.sync()
                    log.info("Synced %d global command(s)", len(synced))
            except Exception:
                log.exception("Failed to sync application commands")
        else:
            log.info("Command sync skipped (DISCORD_SYNC_COMMANDS=false)")

    return bot


# ---------------------------------------------------------------------------
# Telegram bot
# ---------------------------------------------------------------------------

TELEGRAM_HELP_TEXT = (
    "📖 A Course in Miracles Bot\n\n"
    "Commands:\n"
    "/acim <number> — Look up a lesson by number (1-365)\n"
    "/acim random — Get a random lesson\n"
    "/acimsearch <keyword> — Search lesson titles by keyword\n\n"
    "Examples:\n"
    "/acim 1\n"
    "/acim random\n"
    "/acimsearch fear"
)


def _run_telegram_bot() -> None:
    """Start the Telegram bot (blocking)."""
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    async def post_init(_application: object) -> None:
        """Start health server after the Telegram app initializes."""
        await start_health_server()

    app.post_init = post_init

    async def start_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE,  # noqa: ARG001
    ) -> None:
        msg = update.effective_message
        if msg is None:
            return
        await msg.reply_text(TELEGRAM_HELP_TEXT)

    async def help_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE,  # noqa: ARG001
    ) -> None:
        msg = update.effective_message
        if msg is None:
            return
        await msg.reply_text(TELEGRAM_HELP_TEXT)

    async def acim_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        msg = update.effective_message
        if msg is None:
            return
        if not context.args:
            await msg.reply_text(
                "Usage: /acim <lesson number 1-365> or /acim random"
            )
            return

        query = context.args[0].strip().lower()
        if query == "random":
            number, rand_title = get_random_lesson()
            await msg.reply_text(f"🎲 Lesson {number}\n{rand_title}")
            return

        try:
            number = int(query)
        except ValueError:
            await msg.reply_text(
                "⚠️ That doesn't look like a lesson number. "
                "Use /acim <number>, /acim random, or /acimsearch <keyword>."
            )
            return

        if not is_valid_lesson(number):
            await msg.reply_text(
                f"⚠️ Lesson number must be between 1 and {TOTAL_LESSONS}."
            )
            return
        looked_up = get_lesson(number)
        if looked_up is None:
            await msg.reply_text("⚠️ Could not find that lesson.")
            return
        await msg.reply_text(f"📖 Lesson {number}\n{looked_up}")

    async def acimsearch_command(
        update: Update, context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        msg = update.effective_message
        if msg is None:
            return
        if not context.args:
            await msg.reply_text("Usage: /acimsearch <keyword>")
            return
        query = " ".join(context.args)
        results = search_lessons(query)
        if not results:
            await msg.reply_text(f'🔍 No lessons found matching "{query}".')
            return
        lines = [f"📖 Lesson {num}: {title}" for num, title in results]
        await msg.reply_text(f'🔍 Results for "{query}":\n' + "\n".join(lines))

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("acim", acim_command))
    app.add_handler(CommandHandler("acimsearch", acimsearch_command))

    log.info("Starting Telegram bot...")
    app.run_polling()


# ---------------------------------------------------------------------------
# Signal handling & graceful shutdown
# ---------------------------------------------------------------------------
def _handle_signal(signum: int, _frame: object) -> None:
    sig_name = signal.Signals(signum).name
    log.info("Received %s — shutting down gracefully...", sig_name)
    raise SystemExit(0)


# ---------------------------------------------------------------------------
# Configuration validation (called from main, not at import time)
# ---------------------------------------------------------------------------
def _validate_config() -> None:
    """Validate configuration and exit with a clear message on errors."""
    if BOT_MODE not in VALID_MODES:
        log.error("BOT_MODE must be 'discord' or 'telegram', got %r", BOT_MODE)
        sys.exit(1)
    if BOT_MODE == "telegram" and not TELEGRAM_TOKEN:
        log.error("TELEGRAM_TOKEN is required for Telegram mode.")
        sys.exit(1)
    if BOT_MODE == "discord" and not DISCORD_TOKEN:
        log.error("DISCORD_TOKEN is required for Discord mode.")
        sys.exit(1)
    log.info("ACIM_SEARCH_MAX_RESULTS=%d", ACIM_SEARCH_MAX_RESULTS)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _validate_config()

    if BOT_MODE == "telegram":
        _run_telegram_bot()
    else:
        bot = _build_discord_bot()
        bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
