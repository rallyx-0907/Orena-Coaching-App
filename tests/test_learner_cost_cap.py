"""Each learner's own daily AI cost cap, by plan (D-251; owner 2026-10-21: "không có trần chung cho app, chỉ có trần cho
từng người dùng theo gói ... pilot là pilot bản product"). One heavy learner never blocks another; at the cap a learner's
paid calls go to the economy model, at the hard ceiling only zero-cost rungs run and a paid-only request is the existing
429 `quota_exhausted`. Per-capability daily caps measure the request's own learner, never everyone."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from writing_coach import policies
from writing_coach.ai import learner_cost, spend_gate
from writing_coach.ai.routing import ProviderTarget
from writing_coach.core.request_context import USER_KEY_CTX

NOW = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
PAID = ProviderTarget("openai", "gpt-4o", 20)
FREE = ProviderTarget("openrouter", "google/gemma-4-31b-it:free")
LOCAL = ProviderTarget("ollama", "gemma3")


class Ledger:
    """`ai_cost_records` per account: {user_key: USD today}, or rows {user_key: [(provider, feature, usd or None)]} read
    with the repository's own exclusions (a row without a price adds 0 and counts as unpriced)."""

    def __init__(self, spend=None, fail=(), rows=None):
        self.spend, self.fail, self.calls, self.rows = dict(spend or {}), set(fail), [], dict(rows or {})
        self.lock = __import__("threading").Lock()

    def __call__(self, user_key, since, *, exclude_providers=(), exclude_features=()):
        self.calls.append((user_key, tuple(exclude_providers)))
        if user_key in self.fail:
            raise RuntimeError("ledger down")
        with self.lock:
            rows = [row for row in self.rows.get(user_key, [])
                    if row[0] not in exclude_providers and row[1] not in exclude_features]
        usd = sum(row[2] for row in rows if row[2] is not None)
        return self.spend.get(user_key, 0.0) + usd, sum(1 for row in rows if row[2] is None)


@pytest.fixture
def world(monkeypatch):
    from writing_coach.product import quota

    plans = {"heavy": "free", "light": "free", "plus-learner": "plus", "pro-learner": "pro"}
    monkeypatch.setattr(quota, "runtime", lambda: SimpleNamespace(
        plan_for=lambda key, strict=True: SimpleNamespace(id=plans.get(key, "free"))))
    ledger = Ledger()
    ticks = iter(range(0, 10**7, 10))
    learner_cost.configure(ledger, monotonic=ticks.__next__, now=lambda: NOW)
    yield ledger
    learner_cost.configure(None)


def as_learner(key):
    return USER_KEY_CTX.set(key)


def test_the_defaults_are_d248s_formula():
    """60% of the monthly price over 30 days at 26,000 VND a dollar: Plus ~0.061, Pro ~0.122; Free 0.02."""
    assert learner_cost.derived_daily_usd("plus") == pytest.approx(79_000 * 0.6 / 26_000 / 30, abs=1e-4)
    assert learner_cost.derived_daily_usd("pro") == pytest.approx(159_000 * 0.6 / 26_000 / 30, abs=1e-4)
    for plan in learner_cost.PLANS:
        assert policies.default(learner_cost.CAP_POLICY.format(plan=plan)) == learner_cost.DEFAULT_DAILY_USD[plan]
        assert learner_cost.daily_cap_usd(plan) == pytest.approx(learner_cost.DEFAULT_DAILY_USD[plan])
    assert learner_cost.daily_cap_usd("premium") == learner_cost.daily_cap_usd("free"), "an unknown plan: the Free cap"


def test_one_heavy_learner_never_blocks_another(world):
    world.spend = {"heavy": 5.0, "light": 0.0}
    assert learner_cost.learner_cost_state("heavy").state == learner_cost.REFUSE
    light = learner_cost.learner_cost_state("light")
    assert light.state == learner_cost.OK and light.cap_usd == pytest.approx(0.02)
    assert learner_cost.admitted_chain([PAID], light) == [PAID]


def test_the_cap_degrades_to_the_economy_model_then_the_hard_ceiling_refuses(world):
    cap = learner_cost.daily_cap_usd("plus")
    hard = cap * policies.value(learner_cost.HARD_POLICY)
    world.spend = {"plus-learner": cap * 0.5}
    assert learner_cost.learner_cost_state("plus-learner").state == learner_cost.OK
    learner_cost.reset()
    world.spend = {"plus-learner": cap}
    degraded = learner_cost.learner_cost_state("plus-learner")
    assert degraded.state == learner_cost.DEGRADE and degraded.economy == ProviderTarget("gemini", "gemini-3.1-flash-lite")
    # the free and local rungs first, then the economy model in place of every other paid rung
    assert learner_cost.admitted_chain([PAID, FREE, LOCAL], degraded) == [
        FREE, LOCAL, ProviderTarget("gemini", "gemini-3.1-flash-lite", 20)]
    assert learner_cost.admitted_chain([FREE], degraded) == [FREE], "a zero-cost chain gets no paid rung added"
    learner_cost.reset()
    world.spend = {"plus-learner": hard}
    refused = learner_cost.learner_cost_state("plus-learner")
    assert refused.state == learner_cost.REFUSE
    assert learner_cost.admitted_chain([PAID, FREE, LOCAL], refused) == [FREE, LOCAL], "zero-cost paths stay uncapped"
    assert learner_cost.admitted_chain([PAID], refused) == []


def test_a_plan_has_its_own_cap(world):
    world.spend = {"pro-learner": 0.08, "plus-learner": 0.08}
    assert learner_cost.learner_cost_state("pro-learner").state == learner_cost.OK          # Pro ~0.122
    assert learner_cost.learner_cost_state("plus-learner").state == learner_cost.DEGRADE    # Plus ~0.061


def test_free_tier_providers_are_not_counted(world):
    learner_cost.learner_cost_state("light")
    assert "groq" in world.calls[-1][1]   # policies cost.free_tier.groq is on by default


def test_faults_degrade_one_learner_and_refuse_nobody(world, monkeypatch):
    world.fail = {"heavy"}
    faulty = learner_cost.learner_cost_state("heavy")
    assert faulty.state == learner_cost.DEGRADE and faulty.fault is True
    assert learner_cost.learner_cost_state("light").state == learner_cost.OK
    from writing_coach.product import quota

    def broken(key, strict=True):
        raise RuntimeError("subscriptions down")

    monkeypatch.setattr(quota, "runtime", lambda: SimpleNamespace(plan_for=broken))
    state = learner_cost.learner_cost_state("plus-learner")
    assert state.plan == "free" and state.fault is True and state.state == learner_cost.OK


def test_no_account_and_no_ledger_have_no_learner_cap(world):
    assert learner_cost.learner_cost_state("local").state == learner_cost.OK
    token = as_learner("legacy")
    try:
        assert learner_cost.learner_cost_state().state == learner_cost.OK
    finally:
        USER_KEY_CTX.reset(token)
    learner_cost.configure(None)
    assert learner_cost.learner_cost_state("heavy").state == learner_cost.OK


@pytest.fixture
def app_module():
    import app

    return app   # imported before `world`, which then installs its own ledger and plans


def test_the_refusal_is_the_existing_quota_exhausted_shape_and_names_no_figure(app_module, world):
    world.spend = {"heavy": 5.0}
    error = learner_cost.LearnerCostCapReached(learner_cost.learner_cost_state("heavy"))
    response = asyncio.run(app_module._learner_cost_cap_reached(None, error))
    detail = json.loads(response.body)["detail"]
    assert response.status_code == 429 and int(response.headers["retry-after"]) >= 1
    assert detail["category"] == "quota_exhausted" and detail["retryable"] is False
    context = detail["context"]
    assert context["feature"] == "ai.daily_cost" and context["window"] == "day" and context["plan"] == "free"
    assert context["resets_at"] == "2026-10-22T00:00:00Z" and context["upgrade"] == "#/plan/pricing"
    assert not {"used", "limit", "spent_usd", "cap_usd"} & set(context), "D-248: the ceiling stays hidden"
    world.spend = {"pro-learner": 5.0}
    paid = learner_cost.LearnerCostCapReached(learner_cost.learner_cost_state("pro-learner")).facts()
    assert "upgrade" not in paid, "only a Free learner is pointed to the plans"
    assert error.failure_class == "not_counted", "never counted as a provider outage"


def test_the_router_refuses_a_paid_only_chain_at_the_hard_ceiling(world, monkeypatch):
    """platform.generate_structured: the chain is narrowed before any rung is asked."""
    import inspect

    from writing_coach.ai import platform

    source = inspect.getsource(platform.generate_structured)
    assert "learner_cost_state()" in source and "admitted_chain(chain, learner)" in source
    assert "LearnerCostCapReached(learner)" in source


class CapabilityRepository:
    def __init__(self):
        self.account_spend = {}
        self.capability_spend = 0.0

    def ai_spend_since_for_account(self, user_key, since, *, capability=None, provider=None, model=None,
                                   exclude_providers=()):
        return self.account_spend.get(user_key, 0.0), 0

    def ai_spend_since_for_capability(self, capability, since, *, provider=None, model=None):
        return self.capability_spend, 0


def test_a_capability_cap_measures_the_requests_own_learner(monkeypatch):
    """word_translation's paid standby (0.5 USD a day by default): one learner at it does not stop another."""
    from writing_coach.ai import platform

    repository = CapabilityRepository()
    monkeypatch.setattr(platform, "_installed_platform_repository", lambda: repository)
    spend_gate.reset()
    repository.account_spend = {"heavy": 0.6, "light": 0.0}
    repository.capability_spend = 0.6   # the whole capability is over: it no longer matters for a learner
    try:
        for key, refused in (("heavy", True), ("light", False)):
            token = as_learner(key)
            try:
                assert spend_gate.paid_refused("word_translation", "word_translation.daily_spend_cap_usd") is refused
            finally:
                USER_KEY_CTX.reset(token)
        # background work (no account) is still measured over the capability: it is not a learner
        assert spend_gate.paid_refused("word_translation", "word_translation.daily_spend_cap_usd") is True
    finally:
        spend_gate.reset()


# ======================================================================================== review of #487 (P1, P2) ==

def test_unpriced_and_local_calls_never_throttle_a_learner(world, caplog):
    """Ollama (local) costs 0 and Ollama Cloud has no published price: neither moves a Free learner to the economy model,
    however many calls; the unpriced ones raise one monitor alert a day."""
    import logging

    world.rows = {"light": [("ollama", "writing_evaluator", None)] * 50
                  + [("ollama-cloud", "writing_evaluator", None)] * 50}
    with caplog.at_level(logging.ERROR):
        state = learner_cost.learner_cost_state("light")
        learner_cost.reset()
        learner_cost.learner_cost_state("light")
    assert state.state == learner_cost.OK and state.spent_usd == 0.0
    alerts = [r for r in caplog.records if "unpriced provider in use" in r.getMessage()]
    assert alerts and alerts[0].levelno == logging.ERROR
    assert "ollama" in learner_cost.uncounted_providers()


def test_audio_rows_with_their_own_meter_do_not_fill_the_text_cap(world):
    """Pronunciation, voice chat, speech recognition and word audio are limited by their own plan meters."""
    world.rows = {"light": [("azure", "pronunciation_evaluator", 0.5), ("gemini", "agent_voice", 0.5),
                            ("groq", "speech_asr", 0.5), ("azure", "word_tts", 0.5)]}
    state = learner_cost.learner_cost_state("light")
    assert state.state == learner_cost.OK and state.spent_usd == 0.0
    learner_cost.reset()
    world.rows["light"].append(("gemini", "writing_evaluator", 0.025))   # text AI does count: past Free's 0.02
    assert learner_cost.learner_cost_state("light").state == learner_cost.DEGRADE
    assert set(learner_cost.METERED_FEATURES) == {"agent_voice", "pronunciation_evaluator", "speech_asr", "word_tts"}


def test_concurrent_calls_reserve_their_cost_so_a_cap_is_not_overshot(world):
    """Twenty threads of one Free learner each ask before any row reaches the ledger: the reservations already held
    stop the rest at the hard ceiling, where the ledger alone would have let every one through."""
    import threading

    estimate, admitted, start = 0.005, [], threading.Barrier(20)
    lock = threading.Lock()

    def one_call():
        start.wait()
        with lock:   # admission and reservation together, as the router's chain does per rung
            state = learner_cost.learner_cost_state("heavy")
            if state.state == learner_cost.REFUSE:
                return
            held = learner_cost.reserve("heavy", estimate)
            admitted.append(held)

    threads = [threading.Thread(target=one_call) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    hard = learner_cost.daily_cap_usd("free") * policies.value(learner_cost.HARD_POLICY)
    assert len(admitted) == int(round(hard / estimate)), "the in-flight sum reaches the hard ceiling, then refuses"
    assert learner_cost.in_flight_usd("heavy") == pytest.approx(len(admitted) * estimate)
    assert learner_cost.learner_cost_state("light").state == learner_cost.OK, "another learner is not touched"
    for held in admitted:
        held.release()
    assert learner_cost.in_flight_usd("heavy") == 0.0
    assert learner_cost.estimate_call_usd("ollama", "gemma3") == 0.0
    assert learner_cost.estimate_call_usd("gemini", "gemini-3.5-flash-lite", input_tokens=1000, output_tokens=100) > 0


def test_a_row_the_recorder_could_not_write_still_counts_and_is_retried(world, caplog):
    import logging

    from writing_coach.ai import account_costs

    class Failing:
        def __init__(self):
            self.ok, self.rows = False, []

        def record_ai_cost(self, user_key, event):
            if not self.ok:
                raise RuntimeError("table down")
            self.rows.append(user_key)
            return True

    clock = [NOW]
    store = Failing()
    recorder = account_costs.AccountCostRecorder(store, now=lambda: clock[0], run=lambda work: None)
    event = {"outcome": "success", "provider": "gemini", "cost": {"state": "estimated", "amount": 0.05}}
    with caplog.at_level(logging.ERROR):
        assert recorder.record("heavy", event) is False
    assert any("ALERT AI cost per account not written" in r.getMessage() for r in caplog.records)
    assert recorder.pending_usd("heavy", NOW.replace(hour=0)) == pytest.approx(0.05)
    previous = account_costs._recorder
    account_costs._recorder = recorder
    try:
        assert learner_cost.learner_cost_state("heavy").state == learner_cost.REFUSE, "the kept row counts meanwhile"
    finally:
        account_costs._recorder = previous
    store.ok, clock[0] = True, NOW.replace(hour=10)   # after the pause: the kept row is written first
    assert recorder.record("heavy", event) is True
    assert store.rows == ["heavy", "heavy"] and recorder.pending_usd("heavy", NOW.replace(hour=0)) == 0.0


def test_a_public_runtime_refuses_to_start_without_the_ledger_wired(world):
    from writing_coach.core.published_promises import enforce_at_start
    from test_published_promises import KEPT, ON, policy

    assert learner_cost.ledger_wired() is True
    assert enforce_at_start({**KEPT, "APP_ENV": "production"}, policy(ON), learner_ledger=learner_cost.ledger_wired) == []
    learner_cost.configure(None)
    with pytest.raises(RuntimeError, match="ledger"):
        enforce_at_start({**KEPT, "APP_ENV": "production"}, policy(ON), learner_ledger=learner_cost.ledger_wired)

    def broken(*args, **kwargs):
        raise NotImplementedError("the per-account AI ledger is PostgreSQL-only")

    learner_cost.configure(broken)
    assert learner_cost.ledger_wired() is False


def test_system_costs_never_reach_a_learner_cap(world):
    """No signed-in account (a background job) and an administrator's own runs are system costs: the monitor only."""
    from writing_coach.ai import account_costs

    assert learner_cost.learner_cost_state("local-admin").state == learner_cost.OK
    recorder = account_costs.AccountCostRecorder(object(), run=lambda work: None)
    for origin in ("operator_test", "configuration"):
        assert recorder.record("heavy", {"outcome": "success", "provider": "gemini", "origin": origin}) is False
    assert recorder.pending_usd("heavy", NOW.replace(hour=0)) == 0.0


def test_a_free_learner_calling_ollama_cloud_20_times_is_never_degraded_or_refused(world):
    """Hermes for the owner (review of #487): Ollama Cloud is credits-based and publishes no per-token price, so its rows
    are `unpriced`. A Free learner at USD 0.02 a day makes 20 calls; after each the state is read fresh from the ledger,
    and the learner is never degraded or refused because of that accounting gap (recorded in D-251)."""
    from writing_coach.ai.pricing import resolve_token_pricing

    assert resolve_token_pricing("ollama-cloud", "gpt-oss:120b") is None, "no confirmed published price: unpriced"
    assert learner_cost.daily_cap_usd("free") == pytest.approx(0.02)
    world.rows = {"light": []}
    for call in range(20):
        world.rows["light"].append(("ollama-cloud", "writing_evaluator", None))
        learner_cost.reset()
        state = learner_cost.learner_cost_state("light")
        assert state.state == learner_cost.OK, f"call {call + 1}: {state.state}"
        assert learner_cost.admitted_chain([ProviderTarget("ollama-cloud", "gpt-oss:120b")], state) == [
            ProviderTarget("ollama-cloud", "gpt-oss:120b")]
    assert state.spent_usd == 0.0