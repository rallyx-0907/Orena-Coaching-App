from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESCUE = REPO_ROOT / "scripts" / "grammar_rescue_agent.ps1"


def test_codex_rescue_uses_path_python_for_focused_pytest() -> None:
    text = RESCUE.read_text(encoding="utf-8")

    assert "Inside Codex, run focused tests with `python -m pytest`" in text
    assert "Do not use `.venv`, `py`, or a hard-coded Python interpreter path." in text
