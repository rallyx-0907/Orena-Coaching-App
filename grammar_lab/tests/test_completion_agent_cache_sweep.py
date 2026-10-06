from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLETION = REPO_ROOT / "scripts" / "grammar_completion_agent.ps1"


def test_completion_agent_sweeps_all_ready_ids_from_cache_before_paid_generation() -> None:
    text = COMPLETION.read_text(encoding="utf-8")

    assert "function Get-ReadyPointIds" in text
    assert '"corpus-plan", "--lang", $Language, "--json"' in text
    assert '$readyPointIds = @(Get-ReadyPointIds -Language $language)' in text
    assert 'foreach ($readyPointId in $readyPointIds)' in text
    assert 'Invoke-Corpus -Language $language -PointId $readyPointId -CacheOnly' in text

    sweep_start = text.index('$readyPointIds = @(Get-ReadyPointIds -Language $language)')
    sweep_end = text.index('if (-not $AllowPaidCandidates)', sweep_start)
    sweep = text[sweep_start:sweep_end]

    assert 'foreach ($readyPointId in $readyPointIds)' in sweep
    assert '$uncachedPointIds' in sweep
    assert 'cache-only mode: no cached completion' in sweep
    assert 'Invoke-Rescue -PointId $readyPointId' in sweep

    paid_start = text.index('if (-not $AllowPaidCandidates)', sweep_start)
    assert paid_start > sweep_start


def test_completion_agent_reports_uncached_count_when_paid_generation_is_disabled() -> None:
    text = COMPLETION.read_text(encoding="utf-8")
    assert 'Free cache sweep complete' in text
    assert '$uncachedPointIds.Count' in text
