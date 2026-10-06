from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESCUE = REPO_ROOT / "scripts" / "grammar_rescue_agent.ps1"


def test_codex_rescue_passes_outer_python_executable_into_codex() -> None:
    text = RESCUE.read_text(encoding="utf-8")

    assert 'python -c "import sys; print(sys.executable)"' in text
    assert '[string]$PythonExecutable' in text
    assert 'ORENA_PYTHON' in text
    assert 'Use the exact interpreter in `$env:ORENA_PYTHON` for focused tests' in text
    assert 'Do not use `.venv`, `py`, or a bare `python` command inside Codex.' in text
