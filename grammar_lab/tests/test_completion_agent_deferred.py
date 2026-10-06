from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "grammar_completion_agent.ps1"


def test_blocked_rescue_is_deferred_instead_of_stopping_the_batch() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "grammar_completion_deferred.txt" in text
    assert "function Get-DeferredPointIds" in text
    assert "function Add-DeferredPointId" in text
    assert "$deferredPointIds" in text
    assert "$attemptedPointIds" in text
    assert "RESCUE_BLOCKED" in text
    assert "RESCUE_NO_CHANGE" in text
    assert "DEFERRED:" in text

    # Rescue must return both status and text so the caller can distinguish a
    # truthful content block from infrastructure failures.
    assert "$text = ($output | Out-String)" in text
    assert "ExitCode = $exitCode; Text = $text" in text

    # MaxPoints is a cap on unique attempted points, including blocked ones,
    # not only on successful writes.
    assert "$remainingPointSlots = $MaxPoints - $attemptedPointIds.Count" in text
    assert "$attemptedPointIds.Add($readyPointId)" in text

    # Deferred points must be skipped on later runs so the same cached
    # candidate does not consume Codex quota again before its contract changes.
    assert "$deferredPointIds.Contains($_)" in text
    assert "Add-DeferredPointId -PointId $pointId" in text
