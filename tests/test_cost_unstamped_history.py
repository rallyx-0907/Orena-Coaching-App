"""D-220 (PROPOSED): events written before D-219 carry no tier stamp. The flag's history places them: a paid provider's
past spend is real, a free plan's is free, a history that cannot say stays unknown, and no cap moves."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from tests.policy_support import MemoryPolicyStore, installed
from writing_coach import cost_tier
from writing_coach.ai import platform
from writing_coach.media_spend import KIND_AI, KIND_ASR, SpendCapReached, SpendLedger

NOON = datetime(2026, 10, 10, 12, tzinfo=UTC)
CURRENT = {"groq": True, "supadata": True, "gemini": False}


def change(when, key, before, after):
    return {"created_at": when, "payload": {"changes": {key: {"from": before, "to": after, "reset": False}}}}


def row(provider, usd, capability="word_translation", day="2026-10-09"):
    return {"day": day, "capability": capability, "provider": provider, "model": "m", "calls": 1, "failures": 0,
            "priced_calls": 1, "unpriced_calls": 0, "prompt_tokens": 5, "completion_tokens": 5, "audio_seconds": 0.0,
            "usd": usd, "usd_real": 0.0, "usd_free": 0.0, "usd_unknown": usd}


class Repository:
    """A fake platform repository: the unstamped amount of every row, whatever the piece."""

    def __init__(self, rows):
        self.rows = rows

    def ai_unstamped_cost_rows(self, start, end):
        return [{k: r[k] for k in ("day", "capability", "provider", "model")} | {"usd": r["usd_unknown"]}
                for r in self.rows if r["usd_unknown"]]


def place(rows, timeline, *, since=NOON - timedelta(days=5), now=NOON + timedelta(days=5)):
    return platform._place_unstamped_rows(Repository(rows), rows, timeline, since, now)


def test_past_paid_gemini_usage_counts_as_real_spend():
    timeline = cost_tier.timeline_from_audit([], current=CURRENT)
    rows = place([row("gemini", 0.8)], timeline)
    assert (rows[0]["usd_real"], rows[0]["usd_free"], rows[0]["usd_unknown"]) == (0.8, 0.0, 0.0)


def test_a_provider_with_no_flag_such_as_azure_speech_is_real_spend():
    timeline = cost_tier.timeline_from_audit([], current=CURRENT)
    rows = place([row("azure-speech", 0.11, "pronunciation_evaluator")], timeline)
    assert (rows[0]["usd_real"], rows[0]["usd_unknown"]) == (0.11, 0.0)


def test_past_groq_usage_on_an_untouched_free_flag_is_free():
    timeline = cost_tier.timeline_from_audit([], current=CURRENT)
    rows = place([row("groq", 0.32)], timeline)
    assert (rows[0]["usd_real"], rows[0]["usd_free"], rows[0]["usd_unknown"]) == (0.0, 0.32, 0.0)


def test_an_ambiguous_history_stays_unknown():
    # Groq is stored ON by an administrator but no audit row explains it: it must not be called free.
    timeline = cost_tier.timeline_from_audit([], current=CURRENT, stored=frozenset({"groq"}))
    rows = place([row("groq", 0.32), row("", 0.05, "x")], timeline)
    assert rows[0]["usd_unknown"] == 0.32 and rows[0]["usd_free"] == 0.0
    assert rows[1]["usd_unknown"] == 0.05  # an event that names no provider cannot be placed


def test_the_history_decides_before_and_after_a_change():
    flip = NOON
    timeline = cost_tier.timeline_from_audit([change(flip, "cost.free_tier.gemini", True, False)], current=CURRENT)
    before = place([row("gemini", 1.0, day="2026-10-09")], timeline, since=NOON - timedelta(days=2),
                   now=NOON - timedelta(hours=1))
    assert before[0]["usd_free"] == 1.0
    after = place([row("gemini", 1.0)], timeline, since=NOON + timedelta(hours=1), now=NOON + timedelta(days=1))
    assert after[0]["usd_real"] == 1.0


def test_stamped_amounts_are_never_reclassified():
    timeline = cost_tier.timeline_from_audit([], current=CURRENT)
    stamped = row("gemini", 0.0)
    stamped.update(usd=2.0, usd_free=2.0)  # stamped free: no unstamped amount to move
    out = place([stamped], timeline)
    assert out[0]["usd_free"] == 2.0 and out[0]["usd_real"] == 0.0


def test_the_total_is_untouched_so_no_cap_moves():
    timeline = cost_tier.timeline_from_audit([], current=CURRENT)
    rows = place([row("gemini", 0.8), row("groq", 0.2)], timeline)
    assert sum(r["usd"] for r in rows) == pytest.approx(1.0)
    report = platform.cost_report(rows, days=7, since=NOON)
    assert report["totals"]["usd"] == pytest.approx(1.0)
    assert report["totals"]["usd_real"] == pytest.approx(0.8) and report["totals"]["usd_free"] == pytest.approx(0.2)


def test_the_media_ledger_places_unstamped_events_by_history_and_caps_do_not_move(tmp_path):
    path = tmp_path / "spend.json"
    now = datetime.now(UTC).isoformat()
    old = [{"at": now, "kind": "ai", "usd": 0.5, "batch_id": "o", "provider": "groq"},
           {"at": now, "kind": "ai", "usd": 0.25, "batch_id": "o", "provider": "gemini"},
           {"at": now, "kind": "ai", "usd": 0.125, "batch_id": "o"}]
    path.write_text(json.dumps({"schema_version": 1, "events": old}), encoding="utf-8")
    timeline = cost_tier.timeline_from_audit([], current=CURRENT)
    with installed(MemoryPolicyStore({"media.batch_cap_ai_usd": 1.0})):
        spend = SpendLedger(path)
        plain = spend.totals(days=1)
        placed = spend.totals(days=1, tier_at=timeline.tier_at)
        assert plain["unknown_tier_usd"] == 0.875  # without a history nothing is placed
        assert (placed["real_usd"], placed["free_tier_usd"], placed["unknown_tier_usd"]) == (0.25, 0.5, 0.125)
        by = {r["provider"]: r for r in placed["by_provider"]}
        assert by["gemini"]["real_usd"] == 0.25 and by["groq"]["free_tier_usd"] == 0.5
        with pytest.raises(SpendCapReached):  # the batch cap still counts all 0.875 whatever the tier
            spend.check(KIND_AI, "o", 0.2)
        spend.check(KIND_ASR, "o", 0.0)
