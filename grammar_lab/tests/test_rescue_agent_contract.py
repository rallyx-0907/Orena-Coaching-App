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


def test_codex_rescue_stops_immediately_on_blocked_or_no_change() -> None:
    text = RESCUE.read_text(encoding="utf-8")

    assert 'return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }' in text
    assert '$agent = Invoke-CodexRepair' in text
    assert '$agent.Text -match "(?m)^RESCUE_BLOCKED\\s*$"' in text
    assert '$agent.Text -match "(?m)^RESCUE_NO_CHANGE\\s*$"' in text
    assert 'Stopping immediately; another identical Codex cycle would not add evidence.' in text
