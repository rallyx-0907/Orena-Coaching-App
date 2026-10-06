from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLETION = REPO_ROOT / "scripts" / "grammar_completion_agent.ps1"


def test_completion_agent_sweeps_selected_ready_ids_from_cache_before_paid_generation() -> None:
    text = COMPLETION.read_text(encoding="utf-8")

    assert "function Get-ReadyPointIds" in text
    assert "corpus-plan --lang $Language --json" in text
    assert "Get-ReadyPointIds -Language $language |" in text
    assert 'foreach ($readyPointId in $readyPointIds)' in text
    assert 'Invoke-Corpus -Language $language -PointId $readyPointId -CacheOnly' in text

    sweep_start = text.index('Get-ReadyPointIds -Language $language |')
    sweep_end = text.index('if (-not $AllowPaidCandidates)', sweep_start)
    sweep = text[sweep_start:sweep_end]

    assert 'foreach ($readyPointId in $readyPointIds)' in sweep
    assert '$uncachedPointIds' in sweep
    assert 'Test-CacheMiss -Text $probe.Text' in sweep
    assert '$rescuePointIds' in sweep
    assert 'cache-only mode:' in text
    assert 'no cached completion' in text

    paid_start = text.index('if (-not $AllowPaidCandidates)', sweep_start)
    assert paid_start > sweep_start


def test_completion_agent_reports_uncached_count_when_paid_generation_is_disabled() -> None:
    text = COMPLETION.read_text(encoding="utf-8")
    assert 'Free cache sweep complete' in text
    assert '$uncachedPointIds.Count' in text


def test_paid_error_verifies_cached_candidate_before_codex_rescue() -> None:
    text = COMPLETION.read_text(encoding="utf-8")

    assert 'function Test-CacheMiss' in text

    paid_start = text.index('--- One authorized one-shot candidate: $pointId ---')
    block = text[paid_start:]

    verify = 'Invoke-Corpus -Language $language -PointId $pointId -CacheOnly'
    rescue = 'Invoke-Rescue -PointId $pointId'
    assert verify in block
    assert rescue in block
    assert block.index(verify) < block.index(rescue)
    assert 'Test-CacheMiss -Text $paidReplay.Text' in block
    assert 'Codex rescue skipped because no cached paid candidate exists.' in block
    assert 'Test-Written -Text $paidReplay.Text -PointId $pointId' in block
