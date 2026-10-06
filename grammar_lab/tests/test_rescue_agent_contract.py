from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESCUE = REPO_ROOT / "scripts" / "grammar_rescue_agent.ps1"


def test_codex_rescue_delegates_pytest_to_outer_wrapper() -> None:
    text = RESCUE.read_text(encoding="utf-8")

    assert "Do not run Python or pytest inside Codex" in text
    assert "The outer wrapper runs the targeted pytest suite after RESCUE_PATCHED" in text
    assert "ORENA_PYTHON" not in text
    assert "[string]$PythonExecutable" not in text
    assert 'python -c "import sys; print(sys.executable)"' not in text


def test_codex_rescue_stops_immediately_on_blocked_or_no_change() -> None:
    text = RESCUE.read_text(encoding="utf-8")

    assert 'return [pscustomobject]@{ ExitCode = $exitCode; Text = $text }' in text
    assert '$agent = Invoke-CodexRepair' in text
    assert '$agent.Text -match "(?m)^RESCUE_BLOCKED\\s*$"' in text
    assert '$agent.Text -match "(?m)^RESCUE_NO_CHANGE\\s*$"' in text
    assert 'Stopping immediately; another identical Codex cycle would not add evidence.' in text
