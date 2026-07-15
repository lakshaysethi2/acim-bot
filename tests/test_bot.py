"""Smoke tests for the ACIM bot."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LESSONS_PATH = ROOT / "data" / "lessons.json"


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
# Bot module tests (import-level)
# ---------------------------------------------------------------------------

class TestBotModule:
    """Validate that the bot module can be imported and load_lessons works."""

    def test_import(self) -> None:
        # Set required env vars so the module doesn't sys.exit
        import os
        os.environ.setdefault("BOT_MODE", "discord")
        os.environ.setdefault("DISCORD_TOKEN", "test-token")
        import bot  # noqa: F401

    def test_load_lessons(self) -> None:
        import os
        os.environ.setdefault("BOT_MODE", "discord")
        os.environ.setdefault("DISCORD_TOKEN", "test-token")
        from bot import load_lessons
        lessons = load_lessons()
        assert len(lessons) == 365
        assert "1" in lessons
        assert "365" in lessons

    def test_get_lesson(self) -> None:
        import os
        os.environ.setdefault("BOT_MODE", "discord")
        os.environ.setdefault("DISCORD_TOKEN", "test-token")
        from bot import get_lesson
        assert get_lesson(1) is not None
        assert get_lesson(365) is not None
        assert get_lesson(0) is None
        assert get_lesson(366) is None


# ---------------------------------------------------------------------------
# Syntax / lint tests
# ---------------------------------------------------------------------------

class TestSyntax:
    """Ensure Python files parse correctly."""

    def test_bot_py_parses(self) -> None:
        source = (ROOT / "bot.py").read_text()
        compile(source, "bot.py", "exec")

    def test_ruff_check(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", str(ROOT / "bot.py")],
            capture_output=True,
            text=True,
        )
        # ruff exits 0 when no issues
        if result.returncode != 0:
            pytest.fail(f"ruff found issues:\n{result.stdout}")
