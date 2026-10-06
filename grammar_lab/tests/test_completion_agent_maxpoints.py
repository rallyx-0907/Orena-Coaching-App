from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "grammar_completion_agent.ps1"


def test_maxpoints_caps_ready_points_before_cache_sweep() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "$remainingPointSlots = $MaxPoints - $processed" in text
    assert "$readyPointIds = @($readyPointIds | Select-Object -First $remainingPointSlots)" in text
    assert "Free cache sweep:" in text

    cap_pos = text.index("$readyPointIds = @($readyPointIds | Select-Object -First $remainingPointSlots)")
    sweep_pos = text.index('Write-Host "--- Free cache sweep:')
    assert cap_pos < sweep_pos
