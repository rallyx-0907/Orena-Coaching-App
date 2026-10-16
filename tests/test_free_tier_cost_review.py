"""Review of PR #245 (D-219): the flag decides for a flagged provider; unknown history is visible, not free."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.policy_support import MemoryPolicyStore, installed
from writing_coach import cost_tier, policies
from writing_coach.media_spend import SpendLedger

NOON = datetime(2026, 10, 10, 12, tzinfo=UTC)


def change(when, key, before, after):
    return {"created_at": when, "payload": {"changes": {key: {"from": before, "to": after, "reset": False}}}}


def _stamped(provider, model):
    from writing_coach.ai import platform

    seen: list[dict] = []

    class Repository:
        def record_ai_operation(self, telemetry):
            seen.append(telemetry)

    previous = platform._platform_repository
    platform._platform_repository = Repository()
    try:
        platform._persist_operation_telemetry({"capability": "word_translation", "outcome": "success",
                                               "provider": provider, "model": model})
    finally:
        platform._platform_repository = previous
    return seen[0]["free_tier"]


def test_a_zero_rate_model_follows_its_providers_flag_not_its_catalogue_entry():
    qwen = "qwen/qwen3.8-27b"
    with installed(MemoryPolicyStore({"cost.free_tier.groq": True})):
        assert _stamped("groq", qwen) is True
    with installed(MemoryPolicyStore({"cost.free_tier.groq": False})):
        assert _stamped("groq", qwen) is False  # the owner moved to a paid plan: later calls are real spend
        assert _stamped("groq", "llama-3.1-8b-instant") is False


def test_a_provider_without_a_flag_falls_back_to_the_model_being_free():
    with installed():
        assert _stamped("openrouter", "vendor/model:free") is True
        assert _stamped("openai", "gpt-4o-mini") is False


def test_a_missing_history_for_a_flag_that_is_on_is_unknown_not_free():
    timeline = cost_tier.timeline_from_audit([], current={"groq": True, "supadata": True, "gemini": False},
                                             stored=frozenset({"groq"}))
    assert timeline.tier_at("groq", NOON) == cost_tier.TIER_UNKNOWN     # stored ON, no row explains it
    assert timeline.tier_at("supadata", NOON) == cost_tier.TIER_FREE    # the default, never changed
    assert timeline.tier_at("gemini", NOON) == cost_tier.TIER_REAL
    explained = cost_tier.timeline_from_audit([change(NOON, "cost.free_tier.groq", False, True)],
                                              current={"groq": True}, stored=frozenset({"groq"}))
    assert explained.tier_at("groq", NOON + timedelta(hours=1)) == cost_tier.TIER_FREE
    assert explained.tier_at("groq", NOON - timedelta(hours=1)) == cost_tier.TIER_REAL


def test_supadata_requests_are_counted_by_tier(tmp_path):
    with installed():
        spend = SpendLedger(tmp_path / "spend.json")
        spend.reserve_request(5, media_id="a", provider="supadata")
        spend.reserve_request(5, media_id="b", provider="supadata")
        policies.save({"set": {"cost.free_tier.supadata": False}}, actor="admin")
        spend.reserve_request(5, media_id="c", provider="supadata")
        row = {r["provider"]: r for r in spend.totals(days=1)["by_provider"]}["supadata"]
    assert row["requests_by_tier"] == {"real": 1, "free": 2, "unknown": 0}


def test_the_stored_flag_is_known_to_the_policies_module():
    with installed(MemoryPolicyStore({"cost.free_tier.groq": True})):
        assert policies.has_admin_value("cost.free_tier.groq") is True
        assert policies.has_admin_value("cost.free_tier.gemini") is False
