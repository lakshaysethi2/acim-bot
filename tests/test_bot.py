"""Smoke tests for the ACIM bot."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LESSONS_PATH = ROOT / "data" / "lessons.json"

# Ensure the project root is on sys.path so import bot works
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Lesson data tests
# ---------------------------------------------------------------------------


class TestLessonsJson:
    """Validate the lessons.json data file."""

    @pytest.fixture()
    def lessons(self) -> dict[str, str]:
        with LESSONS_PATH.open(encoding="utf-8") as f:
            return json.load(f)

    def test_has_365_entries(self, lessons: dict[str, str]) -> None:
        assert len(lessons) == 365

    def test_all_keys_present(self, lessons: dict[str, str]) -> None:
        for i in range(1, 366):
            assert str(i) in lessons, f"Missing lesson {i}"

    def test_no_empty_titles(self, lessons: dict[str, str]) -> None:
        for i in range(1, 366):
            assert lessons[str(i)].strip(), f"Empty title for lesson {i}"

    def test_no_extra_keys(self, lessons: dict[str, str]) -> None:
        for key in lessons:
            assert key.isdigit(), f"Non-numeric key: {key!r}"


# ---------------------------------------------------------------------------
# Bot module tests — use monkeypatch to set env vars before import
# ---------------------------------------------------------------------------


class TestBotModule:
    """Validate that the bot module can be imported and core functions work."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_MODE", "discord")
        monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    def test_import(self) -> None:
        import bot  # noqa: F401

    def test_load_lessons(self) -> None:
        from bot import load_lessons

        lessons = load_lessons()
        assert len(lessons) == 365
        assert "1" in lessons
        assert "365" in lessons

    def test_get_lesson(self) -> None:
        from bot import get_lesson

        assert get_lesson(1) is not None
        assert get_lesson(365) is not None
        assert get_lesson(0) is None
        assert get_lesson(366) is None

    def test_total_lessons_constant(self) -> None:
        from bot import TOTAL_LESSONS

        assert TOTAL_LESSONS == 365

    def test_validate_config_rejects_bad_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("BOT_MODE", "discrod")
        import importlib

        import bot

        importlib.reload(bot)
        with pytest.raises(SystemExit):
            bot._validate_config()


# ---------------------------------------------------------------------------
# Random lesson tests
# ---------------------------------------------------------------------------


class TestRandom:
    """Validate random lesson selection."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_MODE", "discord")
        monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    def test_get_random_lesson_in_range(self) -> None:
        from bot import TOTAL_LESSONS, get_random_lesson

        for _ in range(20):
            number, title = get_random_lesson()
            assert 1 <= number <= TOTAL_LESSONS
            assert title.strip()

    def test_get_random_lesson_matches_data(self) -> None:
        from bot import get_lesson, get_random_lesson

        number, title = get_random_lesson()
        assert get_lesson(number) == title


# ---------------------------------------------------------------------------
# Search tests
# ---------------------------------------------------------------------------


class TestSearch:
    """Validate lesson search functionality."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_MODE", "discord")
        monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    def test_search_fear(self) -> None:
        from bot import search_lessons

        results = search_lessons("fear")
        assert len(results) > 0
        for num, title in results:
            assert "fear" in title.lower()
            assert 1 <= num <= 365

    def test_search_returns_max_results(self) -> None:
        from bot import search_lessons

        results = search_lessons("God", max_results=2)
        assert len(results) <= 2

    def test_search_no_results(self) -> None:
        from bot import search_lessons

        results = search_lessons("xyznonexistent123")
        assert len(results) == 0

    def test_search_case_insensitive(self) -> None:
        from bot import search_lessons

        lower = search_lessons("fear", max_results=1)
        upper = search_lessons("FEAR", max_results=1)
        assert lower == upper

    def test_search_results_ordered_by_number(self) -> None:
        from bot import search_lessons

        results = search_lessons("fear")
        numbers = [num for num, _ in results]
        assert numbers == sorted(numbers)

    def test_search_empty_query(self) -> None:
        from bot import search_lessons

        assert search_lessons("") == []
        assert search_lessons("   ") == []

    def test_search_max_results_env(self) -> None:
        from bot import ACIM_SEARCH_MAX_RESULTS, DEFAULT_SEARCH_MAX

        assert ACIM_SEARCH_MAX_RESULTS == DEFAULT_SEARCH_MAX

    def test_search_default_cap(self) -> None:
        from bot import ACIM_SEARCH_MAX_RESULTS, search_lessons

        # "I" appears in many titles — should hit the default cap
        results = search_lessons("I")
        assert len(results) <= ACIM_SEARCH_MAX_RESULTS


# ---------------------------------------------------------------------------
# Discord command structure tests
# ---------------------------------------------------------------------------


class TestDiscordCommands:
    """Validate Discord slash-command group structure."""

    @pytest.fixture(autouse=True)
    def _setup_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_MODE", "discord")
        monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    def test_acim_group_has_expected_subcommands(self) -> None:
        from bot import _build_discord_bot

        bot = _build_discord_bot()
        # Walk the command tree for the acim group
        cmds = {c.name: c for c in bot.tree.get_commands()}
        assert "acim" in cmds
        group = cmds["acim"]
        sub_names = {c.name for c in group.commands}  # type: ignore[attr-defined]
        assert sub_names == {"lesson", "random", "search"}


# ---------------------------------------------------------------------------
# Syntax / lint tests
# ---------------------------------------------------------------------------


class TestSyntax:
    """Ensure Python files parse correctly and pass lint checks."""

    def test_bot_py_parses(self) -> None:
        source = (ROOT / "bot.py").read_text()
        compile(source, "bot.py", "exec")

    def test_ruff_check(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(ROOT / "bot.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail(f"ruff found issues:\n{result.stdout}")
