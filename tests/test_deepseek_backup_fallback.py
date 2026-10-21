"""PR CA: the DeepSeek backup behind a Gemini that is out of its monthly spend cap (:8000, 2026-10-20).

The owner's supervisor put `deepseek/deepseek-flash` behind Gemini on nine capabilities because every Gemini call
answered HTTP 429 "Your project has exceeded its monthly spending cap". These tests run that exact chain through the
real learner runtime (`AI_RUNTIME_MODE=capability`, `platform.generate_structured`) with the real OpenAI-compatible
adapters; only the HTTP transport is faked (no network, no key). They hold:

- learner_dictionary and writing_evaluator requests reach DeepSeek once Gemini answers the spend-cap 429;
- the breaker opens on that 429, so the next request skips Gemini without calling it;
- the provider switch is in the telemetry;
- the system spend ceiling is charged at DeepSeek's catalogue rate (pricing.py), and an unpriced model is never free;
- D-104 still lets DeepSeek (a paid, non-logging provider) receive learner text;
- an incomplete JSON answer is asked again once, through the spend gate, and both calls are charged.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pytest

import writing_coach.ai.platform as platform
from writing_coach.agent.budget import UNPRICED_ALLOWANCE_USD, DailySpendGuard
from writing_coach.ai import providers as providers_module
from writing_coach.ai import routing, spend_gate
from writing_coach.ai.base import AIProviderResponseInvalid
from writing_coach.ai.capabilities import require_capability
from writing_coach.ai.config import CapabilityConfig, learner_text_refused, validate_capability_config
from writing_coach.ai.pricing import estimate_token_cost, priced_catalogue_models, resolve_token_pricing
from writing_coach.ai.providers import build_providers
from writing_coach.persistence.platform_repository import CapabilityConfigRecord

GEMINI_MODEL = "gemini-3.5-flash-lite"
DEEPSEEK_MODEL = "deepseek-flash"
# The provider's own words and envelope, as Gemini's OpenAI-compatible endpoint sent them on :8000.
GEMINI_SPEND_CAP_BODY = [{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                                    "message": "Your project has exceeded its monthly spending cap. Please go to AI "
                                               "Studio at https://ai.studio/spend to manage your project spend cap."}}]
CAPABILITIES = ("learner_dictionary", "writing_evaluator")
LEARNER_TEXT = "my private essay about my landlord"
PROMPT_TOKENS, COMPLETION_TOKENS = 1_000, 500


class Response:
    def __init__(self, status: int, body: Any) -> None:
        self.status_code, self._body, self.headers = status, body, {}

    def json(self) -> Any:
        return self._body


def chat_answer(content: str) -> Response:
    return Response(200, {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                          "usage": {"prompt_tokens": PROMPT_TOKENS, "completion_tokens": COMPLETION_TOKENS,
                                    "total_tokens": PROMPT_TOKENS + COMPLETION_TOKENS}})


class Transport:
    """The fake `requests.post` of the adapters: Gemini answers its spend-cap 429; DeepSeek answers from a queue."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.deepseek: list[str] = []

    def post(self, url: str, *, headers: dict, json: dict, timeout: float, **_: Any) -> Response:  # noqa: A002
        host = "gemini" if "generativelanguage" in url else "deepseek" if "deepseek" in url else "other"
        self.calls.append({"host": host, "body": json})
        if host == "gemini":
            return Response(429, GEMINI_SPEND_CAP_BODY)
        assert host == "deepseek"
        return chat_answer(self.deepseek.pop(0) if self.deepseek else '{"ok": true}')

    def hosts(self) -> list[str]:
        return [call["host"] for call in self.calls]


class Repository:
    """Capability rows and the AI operation ledger, summed exactly as PostgresPlatformRepository.ai_spend_since does."""

    def __init__(self, configs: dict[str, CapabilityConfig]) -> None:
        self.configs = configs
        self.operations: list[dict[str, Any]] = []

    def initialize(self) -> None:
        pass

    def get_capability_config(self, key: str) -> CapabilityConfigRecord | None:
        config = self.configs.get(key)
        return CapabilityConfigRecord(key, config) if config else None

    def record_ai_operation(self, telemetry: dict[str, Any]) -> None:
        self.operations.append(telemetry)

    def ai_spend_since(self, since: datetime) -> tuple[float, int]:
        usd = sum(float((op.get("cost") or {}).get("amount") or 0) for op in self.operations)
        unpriced = sum(1 for op in self.operations if op.get("outcome") == "success" and op.get("provider")
                       and (op.get("cost") or {}).get("state") != "estimated")
        return usd, unpriced


def backup_config() -> CapabilityConfig:
    return CapabilityConfig(enabled=True, provider="gemini", model=GEMINI_MODEL, backup_provider="deepseek",
                            backup_model=DEEPSEEK_MODEL, temperature=0.0, fallback_policy="none")


@pytest.fixture
def world(monkeypatch):
    for name in ("ORENA_CAPABILITY_ROUTING", "FUNDING_ENFORCEMENT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    transport = Transport()
    monkeypatch.setattr(providers_module.requests, "post", transport.post)
    # Test credentials only (never a real key); the model lists are the ones :8000's keys offer.
    built = build_providers({"gemini": {"api_key": "test-gemini", "models": [GEMINI_MODEL]},
                             "deepseek": {"api_key": "test-deepseek", "models": [DEEPSEEK_MODEL, "deepseek-v4-pro"]}})
    monkeypatch.setattr(platform, "providers", lambda: built)
    repository = Repository({key: backup_config() for key in CAPABILITIES})
    monkeypatch.setattr(platform, "_platform_repository", repository)
    routing.provider_health.reset()
    spend_gate.reset()
    spend_gate.configure_ceiling(2.0, read=repository.ai_spend_since)  # the $2/day ceiling, read from the ledger
    yield type("World", (), {"transport": transport, "repo": repository})
    spend_gate.configure_ceiling(None, read=None)
    spend_gate.reset()
    routing.provider_health.reset()


def ask(capability: str):
    return platform.generate_structured(messages=[{"role": "user", "content": LEARNER_TEXT}],
                                        schema={"type": "object"}, max_output_tokens=200, capability_key=capability)


# ========================================================================================================= pricing ==

def test_deepseek_current_models_are_priced_from_the_official_page():
    flash = resolve_token_pricing("deepseek", "deepseek-flash")
    pro = resolve_token_pricing("deepseek", "deepseek-v4-pro")
    assert (flash.input_per_million, flash.output_per_million) == (0.30, 1.20)   # peak cache-miss input, peak output
    assert (pro.input_per_million, pro.output_per_million) == (1.32, 3.96)
    legacy_alias = resolve_token_pricing("deepseek", "deepseek-v4-flash")
    assert (legacy_alias.input_per_million, legacy_alias.output_per_million) == (0.30, 1.20)  # "billed at the Flash price"
    # the legacy ids still price old ledger rows, but are never offered as a fallback model
    assert resolve_token_pricing("deepseek", "deepseek-chat") is not None
    assert priced_catalogue_models("deepseek") == ["deepseek-flash", "deepseek-v4-pro"]


def test_an_unpriced_model_is_never_free_for_the_spend_gate():
    cost = estimate_token_cost("deepseek", "deepseek-not-on-the-page", {"prompt_tokens": 10, "completion_tokens": 5})
    assert cost["state"] == "unpriced" and cost["amount"] is None
    # A successful unpriced call counts as UNPRICED_ALLOWANCE_USD in every daily guard, the system ceiling included.
    guard = DailySpendGuard(cap_usd=2.0, read=lambda since: (1.995, 1))
    assert guard() is not None, "1.995 USD + one unpriced call reaches a 2 USD cap"
    assert UNPRICED_ALLOWANCE_USD > 0


def test_an_unpriced_backup_answer_is_charged_the_allowance_through_the_live_path(world, monkeypatch):
    world.repo.configs["learner_dictionary"] = CapabilityConfig(
        enabled=True, provider="gemini", model=GEMINI_MODEL, backup_provider="deepseek",
        backup_model="deepseek-not-on-the-page", temperature=0.0, fallback_policy="none")
    built = platform.providers()
    built["deepseek"].allowed_models.append("deepseek-not-on-the-page")
    ask("learner_dictionary")
    answered = [op for op in world.repo.operations if op["outcome"] == "success"][-1]
    assert answered["provider"] == "deepseek" and answered["cost"]["state"] == "unpriced"
    usd, unpriced = world.repo.ai_spend_since(datetime.now())
    assert unpriced == 1, "the unpriced success is counted by the ceiling's ledger at the allowance, never as zero"


# ======================================================================================================== fallback ==

@pytest.mark.parametrize("capability", CAPABILITIES)
def test_a_learner_request_reaches_deepseek_when_gemini_is_out_of_its_spend_cap(world, capability):
    result = ask(capability)
    assert (result.provider, result.model, result.data) == ("deepseek", DEEPSEEK_MODEL, {"ok": True})
    assert world.transport.hosts() == ["gemini", "deepseek"]
    sent = world.transport.calls[-1]["body"]
    assert sent["model"] == DEEPSEEK_MODEL and sent["response_format"] == {"type": "json_object"}  # DeepSeek JSON mode


def test_the_breaker_opens_and_the_next_request_skips_gemini(world):
    ask("learner_dictionary")
    # a project spend cap stands the model down at its first failure (PR BZ holds a spend cap per model)
    assert routing.provider_health.down_reason("gemini", GEMINI_MODEL) == "spend_cap"
    assert routing.provider_health.is_available("gemini", GEMINI_MODEL) is False
    ask("writing_evaluator")
    assert world.transport.hosts() == ["gemini", "deepseek", "deepseek"], "Gemini is not called while it is down"
    answered = [op for op in world.repo.operations if op["outcome"] == "success"]
    assert [op["provider_switch"] for op in answered] == [
        {"from": "gemini", "to": "deepseek", "reason": "spend_cap", "trigger": "failed"},
        {"from": "gemini", "to": "deepseek", "reason": "spend_cap", "trigger": "down"},
    ]
    failed = [op for op in world.repo.operations if op["outcome"] == "failure"]
    assert failed[0]["provider"] == "gemini" and failed[0]["failure_class"] == "spend_cap"
    assert failed[1]["failure_class"] == "not_counted"   # the skipped rung is not a second failure
    assert LEARNER_TEXT not in json.dumps(world.repo.operations)


def test_the_spend_ceiling_is_charged_at_deepseeks_rate(world):
    ask("learner_dictionary")
    answered = [op for op in world.repo.operations if op["outcome"] == "success"][-1]
    expected = (PROMPT_TOKENS * 0.30 + COMPLETION_TOKENS * 1.20) / 1_000_000
    assert answered["cost"]["state"] == "estimated"
    assert answered["cost"]["amount"] == pytest.approx(expected)
    assert answered["cost"]["provenance"]["model"] == DEEPSEEK_MODEL
    usd, unpriced = world.repo.ai_spend_since(datetime.now())
    assert usd == pytest.approx(expected) and unpriced == 0
    assert spend_gate.ceiling_status()["ceiling_usd"] == 2.0


def test_the_monitor_alerts_but_never_stops_the_paid_backup(world, monkeypatch):
    """D-251: the system total past its threshold is an alert, not a lock: the next learner is still answered."""
    import writing_coach.agent.budget as budget

    monkeypatch.setattr(budget, "CACHE_SECONDS", 0.0)   # read the ledger at each check, not the 5-second verdict
    spend_gate.configure_ceiling(0.0005, read=world.repo.ai_spend_since)
    ask("learner_dictionary")   # 0.0009 USD at DeepSeek's rate: the threshold is now reached
    status = spend_gate.ceiling_status()
    assert status["reached"] is True and status["severity"] == "high"
    before = len(world.transport.hosts())
    assert ask("writing_evaluator") is not None
    assert len(world.transport.hosts()) > before, "a paid rung is still asked past the monitor's threshold"


def test_d104_still_lets_deepseek_receive_learner_text():
    for key in CAPABILITIES:
        definition = require_capability(key)
        assert definition.input_class == "learner_text"
        assert learner_text_refused(definition, "deepseek", DEEPSEEK_MODEL) is False
        validate_capability_config(key, backup_config(), enforce_cap=False)


# =================================================================================================== incomplete JSON ==

def test_an_incomplete_json_answer_is_asked_again_once_and_both_calls_are_charged(world):
    routing.provider_health.record_failure("gemini", "spend_cap")  # Gemini is already down: only DeepSeek is asked
    world.transport.deepseek = ['{"ok": tr', '{"ok": true}']
    result = ask("learner_dictionary")
    assert result.data == {"ok": True}
    assert world.transport.hosts() == ["deepseek", "deepseek"]
    malformed = [op for op in world.repo.operations if op.get("error_class") == "provider_response_invalid"]
    assert len(malformed) == 1 and malformed[0]["failure_class"] == "not_counted"   # not a provider failure
    assert malformed[0]["billable_attempt"] is True and malformed[0]["cost"]["state"] == "estimated"
    usd, _ = world.repo.ai_spend_since(datetime.now())
    one_call = (PROMPT_TOKENS * 0.30 + COMPLETION_TOKENS * 1.20) / 1_000_000
    assert usd == pytest.approx(2 * one_call), "the malformed answer and the retry are both charged"
    assert routing.provider_health.down_reason("deepseek") is None


def test_a_second_incomplete_answer_fails_the_rung_and_is_never_asked_a_third_time(world):
    routing.provider_health.record_failure("gemini", "spend_cap")
    world.transport.deepseek = ['{"ok": tr', "", '{"ok": true}']
    with pytest.raises(AIProviderResponseInvalid):
        ask("learner_dictionary")
    assert world.transport.hosts() == ["deepseek", "deepseek"]
    failed = [op for op in world.repo.operations if op["outcome"] == "failure" and op["provider"] == "deepseek"]
    assert [op["failure_class"] for op in failed][-1] == "schema", "the rung fails once, after its one retry"


def test_the_retry_passes_the_spend_gate_again(world, monkeypatch):
    import writing_coach.agent.budget as budget

    routing.provider_health.record_failure("gemini", "spend_cap")
    world.transport.deepseek = ['{"ok": tr', '{"ok": true}']
    monkeypatch.setattr(budget, "CACHE_SECONDS", 0.0)   # read the ledger at each check, not the 5-second verdict
    # The monitor's threshold is reached by the first (malformed) answer's own cost: the retry is admitted again through
    # the gate (never assumed), and D-251's monitor does not refuse it.
    one_call = (PROMPT_TOKENS * 0.30 + COMPLETION_TOKENS * 1.20) / 1_000_000
    spend_gate.configure_ceiling(one_call * 0.99, read=world.repo.ai_spend_since)
    assert ask("learner_dictionary").data == {"ok": True}
    assert world.transport.hosts() == ["deepseek", "deepseek"], "the retry passes the gate: the monitor only alerts"
    assert spend_gate.ceiling_status()["reached"] is True


def test_the_streaming_agent_turn_has_no_json_retry():
    import inspect

    assert "MALFORMED_JSON_RETRIES" not in inspect.getsource(platform.stream_agent_turn)


# ===================================================================== D-251: the learner's own daily cost cap ==

def _learner(state, economy=None):
    from writing_coach.ai import learner_cost

    return learner_cost.LearnerCostState(state, account="heavy", plan="free", resets_at="2026-10-22T00:00:00Z",
                                         economy=economy)


def test_the_learner_cap_degrades_to_the_economy_model_then_refuses_a_paid_only_chain(world, monkeypatch):
    """Gemini primary and DeepSeek backup, both paid, through the real router: at the learner's cap only the economy
    model is asked; at the hard ceiling nothing is sent and the request is that learner's own refusal (the next
    learner, still under their cap, gets the whole chain)."""
    from writing_coach.ai import learner_cost

    economy = routing.ProviderTarget("deepseek", DEEPSEEK_MODEL)
    monkeypatch.setattr(platform._learner_cost, "learner_cost_state", lambda *a: _learner(learner_cost.DEGRADE, economy))
    result = ask("learner_dictionary")
    assert result.provider == "deepseek" and world.transport.hosts() == ["deepseek"], "the paid primary is skipped"
    monkeypatch.setattr(platform._learner_cost, "learner_cost_state", lambda *a: _learner(learner_cost.REFUSE))
    with pytest.raises(learner_cost.LearnerCostCapReached):
        ask("learner_dictionary")
    assert world.transport.hosts() == ["deepseek"], "nothing is sent at the hard ceiling"
    assert world.repo.operations[-1]["failure_class"] == "not_counted", "not a provider outage"
    monkeypatch.setattr(platform._learner_cost, "learner_cost_state", lambda *a: _learner(learner_cost.OK))
    assert ask("learner_dictionary").provider == "deepseek"
    assert world.transport.hosts() == ["deepseek", "gemini", "deepseek"], "another learner: the whole chain"