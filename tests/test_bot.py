"""Smoke tests for the ACIM bot."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LESSONS_PATH = ROOT / "data" / "lessons.json"

# Ensure the project root is on sys.path so `import bot` works
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

    def test_validate_config_rejects_bad_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BOT_MODE", "discrod")
        import importlib
        import bot
        importlib.reload(bot)
        with pytest.raises(SystemExit):
            bot._validate_config()


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
