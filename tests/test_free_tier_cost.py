"""The free-tier cost flag (D-219, PROPOSED; owner decision 2026-10-16).

A per-provider admin policy says the account is on a free plan. Every cost event is stamped with the provider and the
tier in force when it is recorded; a later toggle never rewrites it. An amount is always the list price, so the caps
never change; real spend sums only events stamped free_tier=false and the free-tier value is reported apart. Fakes
only; nothing reaches a network or a database."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from tests.policy_support import MemoryPolicyStore, installed
from writing_coach import cost_tier, policies
from writing_coach.ai.base import sanitize_telemetry
from writing_coach.ai.platform import cost_report
from writing_coach.ai.pricing import estimate_token_cost, is_free_model, list_rate
from writing_coach.media_spend import KIND_AI, KIND_ASR, KIND_SUPADATA, SpendCapReached, SpendLedger


def ledger(tmp_path):
    return SpendLedger(tmp_path / "spend.json")


def events(tmp_path):
    return json.loads((tmp_path / "spend.json").read_text(encoding="utf-8"))["events"]


# ---- 1. the flag is an ordinary admin policy ---------------------------------------------------------------------

def test_the_flags_are_spend_policies_with_the_owners_defaults():
    expected = {"groq": True, "supadata": True, "gemini": False}
    for provider, default in expected.items():
        policy = policies.BY_KEY[f"cost.free_tier.{provider}"]
        assert (policy.group, policy.kind, policy.default, policy.env, policy.danger) == ("spend", "bool", default, "", "")
        assert cost_tier.flag_key(provider) == policy.key
    assert set(cost_tier.PROVIDERS) == set(expected)
    assert cost_tier.flag_key("openai") is None and cost_tier.is_free_tier("openai") is False


def test_an_administrator_can_flip_a_flag_without_confirmation():
    with installed() as store:
        assert cost_tier.is_free_tier("Groq") is True
        policies.save({"set": {"cost.free_tier.groq": False}}, actor="admin")
        assert cost_tier.is_free_tier("groq") is False
        assert store.audits[-1]["payload"]["changes"]["cost.free_tier.groq"] == {"from": True, "to": False, "reset": False}
        assert store.audits[-1]["payload"]["confirmed"] == []


# ---- 2. every event is stamped at record time --------------------------------------------------------------------

def test_a_media_event_carries_its_provider_and_the_tier_then_and_a_later_toggle_rewrites_nothing(tmp_path):
    with installed(MemoryPolicyStore()):
        spend = ledger(tmp_path)
        spend.record(KIND_ASR, 0.01, batch_id="b1", media_id="m1", units=30, provider="groq")
        policies.save({"set": {"cost.free_tier.groq": False}}, actor="admin")
        spend.record(KIND_AI, 0.02, batch_id="b1", media_id="m1", units=1, provider="groq")
        first, second = events(tmp_path)
    assert (first["provider"], first["free_tier"], first["usd"]) == ("groq", True, 0.01)
    assert (second["provider"], second["free_tier"], second["usd"]) == ("groq", False, 0.02)


def test_a_supadata_request_is_stamped_too(tmp_path):
    with installed():
        spend = ledger(tmp_path)
        spend.reserve_request(5, media_id="youtube-x", provider="supadata")
        policies.save({"set": {"cost.free_tier.supadata": False}}, actor="admin")
        spend.reserve_request(5, media_id="youtube-y", provider="supadata")
        a, b = events(tmp_path)
    assert (a["kind"], a["provider"], a["free_tier"]) == (KIND_SUPADATA, "supadata", True)
    assert b["free_tier"] is False


def test_a_provider_with_no_flag_is_real_spend(tmp_path):
    with installed():
        spend = ledger(tmp_path)
        spend.record(KIND_AI, 0.5, batch_id="b", provider="mystery")
        spend.record(KIND_AI, 0.5, batch_id="b", provider="")
    assert [event["free_tier"] for event in events(tmp_path)] == [False, False]


def test_the_environment_stamp_follows_the_ledgers_own_env(tmp_path):
    with installed():
        spend = SpendLedger(tmp_path / "spend.json", env={})
        spend.record(KIND_ASR, 0.01, batch_id="b", provider="gemini")
    assert events(tmp_path)[0]["free_tier"] is False  # gemini defaults off


def test_telemetry_keeps_only_a_boolean_tier():
    base = {"capability": "word_translation", "outcome": "success", "provider": "groq", "model": "m"}
    assert sanitize_telemetry({**base, "free_tier": True})["free_tier"] is True
    assert sanitize_telemetry({**base, "free_tier": False})["free_tier"] is False
    assert "free_tier" not in sanitize_telemetry({**base, "free_tier": "yes"})
    assert "free_tier" not in sanitize_telemetry(base)


def test_the_operation_telemetry_is_stamped_when_it_is_persisted(monkeypatch):
    from writing_coach.ai import platform

    seen: list[dict] = []

    class Repository:
        def record_ai_operation(self, telemetry):
            seen.append(telemetry)

    monkeypatch.setattr(platform, "_platform_repository", Repository())
    event = {"capability": "word_translation", "outcome": "success", "provider": "gemini", "model": "gemini-3.5-flash-lite"}
    with installed():
        platform._persist_operation_telemetry(dict(event))
        policies.save({"set": {"cost.free_tier.gemini": True}}, actor="admin")
        platform._persist_operation_telemetry(dict(event))
        platform._persist_operation_telemetry({**event, "provider": "groq", "model": "x"})
    assert [item["free_tier"] for item in seen] == [False, True, True]


# ---- 3. totals: real spend is only free_tier=false ---------------------------------------------------------------

def test_real_spend_sums_only_unflagged_events_and_free_value_is_apart(tmp_path):
    with installed():
        spend = ledger(tmp_path)
        spend.record(KIND_AI, 0.30, batch_id="b", provider="groq")           # free
        spend.record(KIND_ASR, 0.10, batch_id="b", provider="groq")          # free
        policies.save({"set": {"cost.free_tier.groq": False}}, actor="admin")
        spend.record(KIND_AI, 0.25, batch_id="b", provider="groq")           # real
        spend.reserve_request(5, media_id="m", provider="supadata")          # free, no dollars
        totals = spend.totals(days=7)
        today = spend.summary()
    assert (totals["real_usd"], totals["free_tier_usd"], totals["unknown_tier_usd"]) == (0.25, 0.4, 0.0)
    by = {row["provider"]: row for row in totals["by_provider"]}
    assert by["groq"]["real_usd"] == 0.25 and by["groq"]["free_tier_usd"] == 0.4
    assert by["supadata"]["requests"] == 1 and by["supadata"]["free_tier_usd"] == 0.0
    assert today["today_usd"] == pytest.approx(0.65)
    assert (today["today_real_usd"], today["today_free_tier_usd"]) == (0.25, 0.4)


def test_an_event_written_before_the_stamp_is_unknown_tier_and_in_neither_bucket(tmp_path):
    path = tmp_path / "spend.json"
    old = {"at": datetime.now(UTC).isoformat(), "kind": "ai", "usd": 0.7, "batch_id": "old", "media_id": "", "units": 1.0,
           "provider": "groq"}
    path.write_text(json.dumps({"schema_version": 1, "events": [old]}), encoding="utf-8")
    with installed():
        spend = SpendLedger(path)
        totals = spend.totals(days=1)
        assert (totals["real_usd"], totals["free_tier_usd"], totals["unknown_tier_usd"]) == (0.0, 0.0, 0.7)
        assert cost_tier.tier_of(old) == cost_tier.TIER_UNKNOWN
        spend.record(KIND_AI, 0.1, batch_id="new", provider="groq")
        assert spend.totals(days=1)["unknown_tier_usd"] == 0.7  # the old row is not rewritten by a new write
    assert "free_tier" not in events(tmp_path)[0] and events(tmp_path)[1]["free_tier"] is True


# ---- 4. the caps do not move -------------------------------------------------------------------------------------

@pytest.mark.parametrize("free", [True, False])
def test_a_spend_cap_counts_the_list_price_whatever_the_tier(tmp_path, free):
    with installed(MemoryPolicyStore({"cost.free_tier.groq": free, "media.batch_cap_ai_usd": 1.0})):
        spend = ledger(tmp_path)
        spend.record(KIND_AI, 0.9, batch_id="b", provider="groq")
        spend.check(KIND_AI, "b", 0.05)
        with pytest.raises(SpendCapReached) as reached:
            spend.check(KIND_AI, "b", 0.2)
    assert reached.value.code == "spend_cap_batch_ai" and reached.value.spent == pytest.approx(0.9)


def test_the_daily_cap_counts_free_and_unknown_events_too(tmp_path):
    path = tmp_path / "spend.json"
    legacy = {"at": datetime.now(UTC).isoformat(), "kind": "ai", "usd": 24.9, "batch_id": "old", "provider": "groq"}
    path.write_text(json.dumps({"schema_version": 1, "events": [legacy]}), encoding="utf-8")
    with installed():
        with pytest.raises(SpendCapReached) as reached:
            SpendLedger(path).check(KIND_ASR, "new", 0.2)
    assert reached.value.code == "spend_cap_day"


# ---- 5. one price source -----------------------------------------------------------------------------------------

def test_the_catalogue_and_the_media_ledger_agree_on_the_qwen_price():
    assert list_rate("groq", "qwen/qwen3.8-27b") == (0.80, 4.00)
    assert policies.media_ai_model_rate("qwen/qwen3.8-27b") == (0.80, 4.00)
    cost = estimate_token_cost("groq", "qwen/qwen3.8-27b", {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
    assert (cost["state"], cost["amount"]) == ("estimated", pytest.approx(4.80))
    assert cost["provenance"]["input_per_million"] == 0.8
    # the plan fact is unchanged: the model is still free to call, so routing and prompt logging treat it as free
    assert is_free_model("groq", "qwen/qwen3.8-27b")


def test_a_free_plan_model_without_a_published_price_stays_at_zero_and_has_no_list_rate():
    assert list_rate("groq", "llama-3.1-8b-instant") is None and policies.media_ai_model_rate("unknown/model") is None
    cost = estimate_token_cost("groq", "llama-3.1-8b-instant", {"prompt_tokens": 500, "completion_tokens": 50})
    assert (cost["state"], cost["amount"]) == ("estimated", 0.0)


# ---- 6. the cost report splits by the stamped tier ---------------------------------------------------------------

def row(day, usd, real, free, unknown, **extra):
    base = {"day": day, "capability": "word_translation", "provider": "groq", "model": "qwen/qwen3.8-27b", "calls": 2,
            "failures": 0, "priced_calls": 2, "unpriced_calls": 0, "usd": usd, "prompt_tokens": 10,
            "completion_tokens": 5, "audio_seconds": 0.0, "usd_real": real, "usd_free": free, "usd_unknown": unknown}
    return {**base, **extra}


def test_the_report_totals_real_spend_apart_from_free_tier_value():
    since = datetime(2026, 10, 1, tzinfo=UTC)
    report = cost_report([row("2026-10-16", 1.5, 0.5, 0.75, 0.25), row("2026-10-15", 0.25, 0.0, 0.25, 0.0)], days=7, since=since)
    assert report["totals"] == {"usd": 1.75, "usd_real": 0.5, "usd_free": 1.0, "usd_unknown": 0.25}
    assert report["by_day"][0]["usd_real"] == 0.5 and report["by_day"][1]["usd_free"] == 0.25
    feature = report["by_feature"][0]
    assert (feature["usd"], feature["usd_real"], feature["usd_free"]) == (1.75, 0.5, 1.0)
    assert {gap["code"] for gap in report["gaps"]} >= {"free_tier_tier", "account_tier"}


def test_a_report_row_without_tier_columns_still_reads():
    legacy = {key: value for key, value in row("2026-10-16", 1.0, 0, 0, 0).items() if not key.startswith("usd_")}
    report = cost_report([legacy], days=1, since=datetime(2026, 10, 16, tzinfo=UTC))
    assert report["totals"]["usd"] == 1.0 and report["totals"]["usd_real"] == 0.0


# ---- 7. ai_cost_records has no tier column: the tier is derived from the flag's history ------------------------

NOON = datetime(2026, 10, 10, 12, tzinfo=UTC)


def change(when, key, before, after):
    return {"created_at": when, "payload": {"changes": {key: {"from": before, "to": after, "reset": False}}}}


def test_the_timeline_answers_what_the_flag_was_at_each_instant():
    rows = [change(NOON, "cost.free_tier.groq", True, False), change(NOON + timedelta(days=3), "cost.free_tier.groq", False, True)]
    timeline = cost_tier.timeline_from_audit(rows, current={"groq": True, "supadata": True, "gemini": False})
    assert timeline.is_free("groq", NOON - timedelta(days=1)) is True
    assert timeline.is_free("groq", NOON + timedelta(days=1)) is False
    assert timeline.is_free("groq", NOON + timedelta(days=4)) is True
    assert timeline.is_free("supadata", NOON) is True and timeline.is_free("gemini", NOON) is False
    assert timeline.is_free("openai", NOON) is False
    assert timeline.boundaries(NOON - timedelta(days=5), NOON + timedelta(days=5)) == [NOON, NOON + timedelta(days=3)]
    assert timeline.boundaries(NOON, NOON + timedelta(days=1)) == []


def test_the_timeline_reads_the_audit_rows_a_real_save_writes():
    with installed() as store:
        policies.save({"set": {"cost.free_tier.groq": False, "cost.free_tier.gemini": True}}, actor="admin")
        audit = [{"created_at": NOON, "payload": item["payload"]} for item in store.audits]
        timeline = cost_tier.timeline_from_audit(audit, current={"groq": False, "supadata": True, "gemini": True})
    assert timeline.is_free("groq", NOON - timedelta(hours=1)) is True
    assert timeline.is_free("groq", NOON + timedelta(hours=1)) is False
    assert timeline.is_free("gemini", NOON - timedelta(hours=1)) is False


def test_a_flag_pinned_by_the_environment_ignores_the_history():
    rows = [change(NOON, "cost.free_tier.groq", False, True)]
    timeline = cost_tier.timeline_from_audit(rows, current={"groq": False}, pinned=frozenset({"groq"}))
    assert timeline.is_free("groq", NOON - timedelta(days=1)) is False
    assert timeline.boundaries(NOON - timedelta(days=1), NOON + timedelta(days=1)) == []


def test_the_archive_repository_reports_no_tiered_costs_and_no_history():
    from writing_coach.persistence.platform_repository import SQLitePlatformRepository

    repository = SQLitePlatformRepository.__new__(SQLitePlatformRepository)
    assert repository.policy_change_history(NOON) == []
    assert repository.ai_costs_by_account_tiered(NOON, NOON, [], lambda *_: True) is None
