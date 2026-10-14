# ruff: noqa: F811
"""word_translation: the paid Groq standby behind a per-capability daily spend cap (D-195 amendment 2026-10-14).

Fake providers only; the ledger and the cap policy are faked too. No network, no key, no live call.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

import writing_coach.ai.platform as platform
from tests.test_ai_router import GEMMA, LAMP, config, env, http_error  # noqa: F401 - `env` is a fixture
from writing_coach import policies
from writing_coach.ai import spend_gate
from writing_coach.ai.base import AICapabilityConfigInvalid, AIProviderError, AIResult
from writing_coach.ai.capabilities import require_capability
from writing_coach.ai.config import CapabilityConfig, validate_capability_config
from writing_coach.ai.pricing import resolve_token_pricing
from writing_coach.ai.router import route, tap

GROQ_MODEL = "llama-3.3-70b-versatile"


class GroqFake:
    id = "groq"
    name = "Groq"
    configured = True

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        self.calls.append(kwargs)
        return AIResult(data={"meaning": "cái đèn"}, provider="groq", model=kwargs["model"],
                        runtime={"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100})

    generate_json = generate_json_once


class Ledger:
    def __init__(self) -> None:
        self.spent = 0.0
        self.unpriced = 0
        self.error: Exception | None = None
        self.reads: list[tuple[str, datetime]] = []


@pytest.fixture
def groq(env, monkeypatch):
    fake = GroqFake()
    monkeypatch.setattr(platform, "providers", lambda: {"openrouter": env.fake, "groq": fake})
    env.repo.config = config(backup_provider="groq", backup_model=GROQ_MODEL)
    ledger = Ledger()

    def spend_since(capability: str, since: datetime) -> tuple[float, int]:
        ledger.reads.append((capability, since))
        if ledger.error:
            raise ledger.error
        return ledger.spent, ledger.unpriced

    monkeypatch.setattr(env.repo, "ai_spend_since_for_capability", spend_since, raising=False)
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0.5)
    spend_gate.reset()
    tap.reset_state()
    yield type("Groq", (), {"fake": fake, "ledger": ledger, "env": env})
    spend_gate.reset()
    tap.reset_state()


def test_a_429_on_the_free_primary_is_answered_by_the_groq_standby_and_the_cost_is_recorded(groq) -> None:
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    result = route("word_translation", LAMP)
    assert (result.output, result.fell_back) == ({"meaning": "cái đèn"}, True)
    assert result.provenance["provider"] == "groq" and result.provenance["tier"] == "paid"
    assert len(groq.fake.calls) == 1
    paid = [op for op in groq.env.repo.operations if op["provider"] == "groq"]
    assert len(paid) == 1 and paid[0]["capability"] == "word_translation" and paid[0]["tier"] == "paid"
    assert paid[0]["cost"]["state"] == "estimated"
    assert paid[0]["cost"]["amount"] == pytest.approx((1000 * 0.59 + 100 * 0.79) / 1_000_000)
    assert groq.ledger.reads[0][0] == "word_translation"


def test_when_the_cap_is_reached_the_standby_is_skipped_and_the_word_is_a_miss(groq) -> None:
    groq.ledger.spent = 0.5
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert groq.fake.calls == []
    skipped = [op for op in groq.env.repo.operations if op["provider"] == "groq"]
    assert [(op["fallback_reason"], op["error_class"], op["tier"]) for op in skipped] == [
        ("budget", "budget_skipped", "paid")
    ]
    spend_gate.reset()
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    assert tap.word_translation_seam("lamp", "A lamp.", [], "en", "vi") is None


def test_an_unpriced_call_counts_against_the_cap_as_a_small_allowance(groq) -> None:
    groq.ledger.spent, groq.ledger.unpriced = 0.45, 6  # 6 x 0.01 USD
    groq.env.fake.script = {GEMMA: [http_error(503)]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert groq.fake.calls == []


def test_an_unreadable_ledger_skips_the_paid_standby(groq) -> None:
    groq.ledger.error = NotImplementedError("the AI spend ledger is PostgreSQL-only")  # the SQLite archive store
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert groq.fake.calls == []


@pytest.mark.parametrize("cap", [0, None])
def test_a_zero_or_missing_cap_skips_the_paid_standby(groq, monkeypatch, cap) -> None:
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: cap)
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert groq.fake.calls == [] and groq.ledger.reads == []


def test_an_unreadable_cap_policy_skips_the_paid_standby(groq, monkeypatch) -> None:
    def broken(key, **_):
        raise policies.PolicyUnavailable("never read")

    monkeypatch.setattr(policies, "value_strict", broken)
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert groq.fake.calls == []


def test_the_free_primary_is_never_gated_by_the_cap(groq) -> None:
    groq.ledger.spent = 99.0
    assert route("word_translation", LAMP).output == {"meaning": "đèn"}
    assert groq.ledger.reads == []


def test_prefetch_never_calls_the_paid_standby(groq) -> None:
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    with pytest.raises(AIProviderError):
        tap.word_translation_prefetch("lamp", "en", "vi")
    assert groq.fake.calls == [] and groq.ledger.reads == []
    # a tap on the same word may use it
    tap.reset_state()
    from writing_coach.ai.router import router as router_module

    router_module.reset_state()
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    assert tap.word_translation_seam("lamp", "A lamp.", [], "en", "vi") == "cái đèn"
    assert len(groq.fake.calls) == 1


# --- validation matrix --------------------------------------------------------------------------------------------

def _config(**kw: Any) -> CapabilityConfig:
    values = {"enabled": False, "provider": "openrouter", "model": GEMMA, "backup_provider": "groq",
              "backup_model": GROQ_MODEL}
    values.update(kw)
    return CapabilityConfig(**values)


def test_the_reviewed_groq_standby_is_valid_with_a_positive_cap(monkeypatch) -> None:
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0.5)
    validate_capability_config("word_translation", _config())
    assert resolve_token_pricing("groq", GROQ_MODEL).input_per_million == 0.59


def test_a_paid_standby_needs_a_positive_cap_to_be_saved_but_a_zero_cap_does_not_break_the_runtime(monkeypatch) -> None:
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0)
    with pytest.raises(AICapabilityConfigInvalid, match="daily spend cap above zero"):
        validate_capability_config("word_translation", _config())
    validate_capability_config("word_translation", _config(), enforce_cap=False)


@pytest.mark.parametrize(
    "overrides",
    [
        {"provider": "groq", "model": GROQ_MODEL, "backup_provider": None, "backup_model": None},  # paid primary
        {"provider": "groq", "model": GROQ_MODEL, "backup_provider": "openrouter", "backup_model": GEMMA},
        {"backup_model": "llama-3.4-405b-versatile"},  # not reviewed, not priced
        {"backup_provider": "openai", "backup_model": "gpt-4o-mini"},  # priced, not reviewed
    ],
)
def test_other_paid_shapes_are_refused(monkeypatch, overrides) -> None:
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0.5)
    with pytest.raises(AICapabilityConfigInvalid):
        validate_capability_config("word_translation", _config(**overrides))


def test_the_input_class_rule_still_keeps_word_translation_to_public_reference() -> None:
    assert require_capability("word_translation").input_class == "public_reference"


def test_other_capabilities_stay_outside_the_tier_rule_and_have_no_gate() -> None:
    validate_capability_config("writing_evaluator", CapabilityConfig(enabled=False, provider="openai", model="gpt-4o-mini"))
    assert platform._budget_gate(require_capability("writing_evaluator")) is None


def test_the_cap_is_a_spend_policy_defaulting_to_fifty_cents() -> None:
    policy = policies.BY_KEY["word_translation.daily_spend_cap_usd"]
    assert (policy.group, policy.default, policy.low) == ("spend", 0.5, 0)
    assert policy.high is not None and policy.env == "WORD_TRANSLATION_DAILY_SPEND_CAP_USD"


# --- the free-plan Groq model: the standby in use now (owner, 2026-10-14) -------------------------------------------

FREE_GROQ = "llama-3.1-8b-instant"


def test_the_groq_free_plan_model_is_a_zero_rate_free_standby_with_provenance() -> None:
    from writing_coach.ai.pricing import estimate_token_cost, is_free_model
    from writing_coach.ai.routing import provider_tier

    entry = resolve_token_pricing("groq", FREE_GROQ)
    assert (entry.input_per_million, entry.output_per_million) == (0.0, 0.0)
    assert "owner-confirmed Groq free plan" in entry.note and "console.groq.com/docs/models" in entry.note
    assert is_free_model("groq", FREE_GROQ) and provider_tier("groq", FREE_GROQ) == "free"
    cost = estimate_token_cost("groq", FREE_GROQ, {"prompt_tokens": 500, "completion_tokens": 50})
    assert (cost["state"], cost["amount"]) == ("estimated", 0.0)


QWEN_GROQ = "qwen/qwen3.8-27b"


def test_the_qwen_groq_model_is_a_zero_rate_free_standby_and_llama_stays_listed() -> None:
    from writing_coach.ai.pricing import is_free_model
    from writing_coach.ai.routing import provider_tier

    entry = resolve_token_pricing("groq", QWEN_GROQ)
    assert (entry.input_per_million, entry.output_per_million) == (0.0, 0.0)
    assert "owner-confirmed Groq free plan" in entry.note
    assert is_free_model("groq", QWEN_GROQ) and provider_tier("groq", QWEN_GROQ) == "free"
    assert resolve_token_pricing("groq", FREE_GROQ) is not None  # kept, though this key's catalogue does not list it


def test_the_qwen_groq_request_switches_thinking_off_and_other_models_are_untouched(monkeypatch) -> None:
    import requests

    from writing_coach.ai import providers as providers_module

    sent: list[dict[str, Any]] = []

    class Response:
        status_code = 200
        headers: dict[str, str] = {}

        def json(self) -> dict[str, Any]:
            return {"choices": [{"message": {"content": '{"meaning": "ha tang"}'}, "finish_reason": "stop"}]}

    monkeypatch.setattr(requests, "post", lambda url, **kw: sent.append(kw["json"]) or Response())
    groq = providers_module.build_providers({"groq": {"api_key": "test-key"}})["groq"]
    for model in (QWEN_GROQ, GROQ_MODEL):
        groq.generate_json_once(messages=[{"role": "user", "content": "x"}], schema={"type": "object"},
                                model=model, max_output_tokens=120, temperature=0.0)
    assert sent[0]["reasoning_effort"] == "none" and sent[0]["reasoning_format"] == "hidden"
    assert "reasoning_effort" not in sent[1] and "reasoning_format" not in sent[1]


def test_the_other_groq_entries_keep_their_paid_prices() -> None:
    paid = resolve_token_pricing("groq", GROQ_MODEL)
    assert (paid.input_per_million, paid.output_per_million) == (0.59, 0.79)
    oss = resolve_token_pricing("groq", "openai/gpt-oss-120b")
    assert (oss.input_per_million, oss.output_per_million) == (0.15, 0.60)


def test_the_free_groq_model_is_a_valid_standby_whatever_the_cap(monkeypatch) -> None:
    for cap in (0, 0.5):
        monkeypatch.setattr(policies, "value_strict", lambda key, cap=cap, **_: cap)
        validate_capability_config("word_translation", _config(backup_model=FREE_GROQ))


def test_a_429_on_the_primary_is_answered_by_the_free_groq_model_without_touching_the_ledger(groq, monkeypatch) -> None:
    groq.env.repo.config = config(backup_provider="groq", backup_model=FREE_GROQ)
    monkeypatch.setattr(policies, "value_strict", lambda key, **_: 0)  # no paid cap at all
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    result = route("word_translation", LAMP)
    assert result.output == {"meaning": "cái đèn"} and result.provenance["tier"] == "free"
    assert groq.ledger.reads == []
    assert [op["cost"]["amount"] for op in groq.env.repo.operations if op["provider"] == "groq"] == [0.0]


def test_prefetch_may_use_the_free_groq_model(groq) -> None:
    groq.env.repo.config = config(backup_provider="groq", backup_model=FREE_GROQ)
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    assert tap.word_translation_prefetch("lamp", "en", "vi") == "cái đèn"
    assert len(groq.fake.calls) == 1


# --- review conditions (P2-1, P2-2, P2-4) --------------------------------------------------------------------------

def test_an_invalid_answer_from_a_paid_rung_is_not_retried_once_the_cap_is_reached(groq) -> None:
    """P2-2: the retry is another paid call, so the gate is asked again before it."""

    answers = [{"meaning": ""}, {"meaning": "cái đèn"}]
    original = groq.fake.generate_json_once

    def scripted(**kwargs):
        result = original(**kwargs)
        result.data = answers.pop(0)
        groq.ledger.spent = 0.5  # this call spent the last of the day's cap...
        spend_gate.reset()  # ...and the gate's few-second verdict cache has expired
        return result

    groq.fake.generate_json_once = scripted
    groq.fake.generate_json = scripted
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert len(groq.fake.calls) == 1


def test_an_invalid_answer_from_a_paid_rung_is_retried_while_the_cap_has_room(groq) -> None:
    answers = [{"meaning": ""}, {"meaning": "cái đèn"}]
    original = groq.fake.generate_json_once

    def scripted(**kwargs):
        result = original(**kwargs)
        result.data = answers.pop(0)
        return result

    groq.fake.generate_json_once = scripted
    groq.fake.generate_json = scripted
    groq.env.fake.script = {GEMMA: [http_error(429)]}
    assert route("word_translation", LAMP).output == {"meaning": "cái đèn"}
    assert len(groq.fake.calls) == 2


def _plane(groq, monkeypatch):
    from writing_coach.ai.control_plane import AIControlPlane

    groq.env.repo.config = config(backup_provider="groq", backup_model=GROQ_MODEL)
    return AIControlPlane(groq.env.repo, provider_factory=lambda: {"openrouter": groq.env.fake, "groq": groq.fake})


@pytest.mark.parametrize("state", ["cap_reached", "ledger_unreadable"])
def test_the_admin_standby_test_does_not_call_a_paid_model_over_the_cap(groq, monkeypatch, state) -> None:
    """P2-1: an operator test is a paid call too; it follows the same gate and says why it did not run."""

    groq.fake.discover_models_live = lambda: pytest.fail("the provider must not be reached")
    if state == "cap_reached":
        groq.ledger.spent = 0.5
    else:
        groq.ledger.error = NotImplementedError("the AI spend ledger is PostgreSQL-only")
    with pytest.raises(AICapabilityConfigInvalid, match="daily spend cap"):
        _plane(groq, monkeypatch)._live_test("word_translation", standby=True)
    assert groq.fake.calls == []


def test_the_admin_primary_test_of_a_free_model_is_not_gated(groq, monkeypatch) -> None:
    groq.ledger.spent = 99.0
    plane = _plane(groq, monkeypatch)
    groq.env.fake.discover_models_live = lambda: [GEMMA]
    groq.env.fake.generate_json_once = lambda **kw: AIResult(
        data={"ok": True, "capability": "word_translation"}, provider="openrouter", model=kw["model"], runtime={}
    )
    assert plane._live_test("word_translation")["ok"] is True
    assert groq.ledger.reads == []


def test_an_unreadable_cap_refuses_to_save_a_paid_standby(monkeypatch) -> None:
    """P2-4: save time reads the cap strictly too."""

    def broken(key, **_):
        raise policies.PolicyUnavailable("never read")

    monkeypatch.setattr(policies, "value_strict", broken)
    with pytest.raises(AICapabilityConfigInvalid, match="unreadable"):
        validate_capability_config("word_translation", _config())
    validate_capability_config("word_translation", _config(backup_model=FREE_GROQ))  # a free standby needs no cap
