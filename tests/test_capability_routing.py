"""PR-MON-7A-first, hermetic: the Ollama Cloud provider, the reviewed-primary policy of a routed capability, the routing
switch, the legacy privacy guard, covered-credit coverage telemetry, and the candidate-model benchmark harness.

No network and no credential: providers are fakes, and the one real `OllamaCloudProvider` test intercepts its HTTP
call. No model id here is a reviewed one; the reviewed allowlists are patched in per test."""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Any

import pytest

import writing_coach.ai.platform as platform
from tests.test_ai_telemetry import Provider, Repository, config
from writing_coach.ai import capabilities as caps
from writing_coach.ai import providers as prov
from writing_coach.ai.base import (
    AICapabilityConfigInvalid,
    AICapabilityNotConfigured,
    AIProviderUnavailable,
    AIResult,
    sanitize_telemetry,
)
from writing_coach.ai.config import ROUTABLE_CAPABILITIES, validate_routed_policy
from writing_coach.ai.routing import provider_tier

CLOUD_MODEL = "candidate-cloud-model"     # a placeholder, not a reviewed model id
PAID = ("openai", "gpt-4o-mini")          # priced in the catalogue (pricing.py)


@pytest.fixture
def reviewed(monkeypatch):
    """Patch `writing_evaluator` to have a reviewed primary/backup, and Ollama Cloud to have a reviewed model."""

    def apply(*, primary=(("ollama-cloud", CLOUD_MODEL),), backup=(PAID,), privacy=(CLOUD_MODEL,), cap=1.0,
              key="writing_evaluator"):
        definition = dataclasses.replace(caps.require_capability(key), reviewed_primary_models=frozenset(primary),
                                         paid_standby_models=frozenset(backup))
        monkeypatch.setattr("writing_coach.ai.config.require_capability",
                            _patched(caps.require_capability, key, definition))
        cloud = dataclasses.replace(prov.get_provider_definition("ollama-cloud"), learner_text_models=frozenset(privacy))
        monkeypatch.setattr("writing_coach.ai.config.get_provider_definition",
                            lambda pid: cloud if pid == "ollama-cloud" else prov.get_provider_definition(pid))
        monkeypatch.setattr("writing_coach.ai.config.resolve_token_pricing", _pricing_with(CLOUD_MODEL))
        from writing_coach import policies

        monkeypatch.setattr(policies, "value_strict", lambda name, **_: cap)
        return definition

    return apply


def _patched(original, key, definition):
    def require(name):
        return definition if name == key else original(name)
    return require


def _pricing_with(model):
    from writing_coach.ai import pricing

    def resolve(provider, name):
        if (provider, name) == ("ollama-cloud", model):
            return pricing.TokenPricing("ollama-cloud", model, "USD", 0.1, 0.2)   # a test reference price
        return pricing.resolve_token_pricing(provider, name)
    return resolve


# ---- the Ollama Cloud provider ---------------------------------------------------------------------------------------

def test_ollama_cloud_is_a_distinct_paid_cloud_provider_never_the_local_adapter(monkeypatch):
    definition = prov.get_provider_definition("ollama-cloud")
    assert definition.kind == "cloud" and definition.learner_text_models == frozenset()
    assert prov.get_provider_definition("ollama").kind == "local"
    assert provider_tier("ollama-cloud", CLOUD_MODEL) == "paid"   # covered by credits or not, never priced $0
    monkeypatch.delenv("OLLAMA_CLOUD_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_CLOUD_MODELS", raising=False)
    assert prov.OllamaCloudProvider().configured is False and prov.OllamaCloudProvider().list_models() == []
    with pytest.raises(AIProviderUnavailable):
        prov.OllamaCloudProvider().generate_json(messages=[], schema={}, model=CLOUD_MODEL, max_output_tokens=10,
                                                 temperature=0.0)


def test_ollama_cloud_sends_its_bearer_credential_and_no_local_options(monkeypatch):
    sent = {}

    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": '{"ok": true}'}, "prompt_eval_count": 120, "eval_count": 30,
                    "done_reason": "stop"}

    def post(url, json, headers, timeout):
        sent.update(url=url, body=json, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(prov.requests, "post", post)
    cloud = prov.OllamaCloudProvider({"api_key": "test-key", "models": [CLOUD_MODEL]})
    result = cloud.generate_json(messages=[{"role": "user", "content": "x"}], schema={"type": "object"},
                                 model=CLOUD_MODEL, max_output_tokens=50, temperature=0.0, timeout=30)
    assert sent["url"] == "https://ollama.com/api/chat" and sent["headers"] == {"Authorization": "Bearer test-key"}
    assert "keep_alive" not in sent["body"] and "num_ctx" not in sent["body"]["options"]
    assert result.provider == "ollama-cloud" and result.runtime["prompt_tokens"] == 120
    assert result.runtime["completion_tokens"] == 30   # priced from the catalogue like any paid call
    local = prov.OllamaProvider({"base_url": "http://local:11434"})
    assert local._request_headers() == {} and local._chat_body({"keep_alive": "30m"}) == {"keep_alive": "30m"}


# ---- the static policy of a routed capability --------------------------------------------------------------------

def routed_config(**overrides):
    values = {"enabled": True, "provider": "ollama-cloud", "model": CLOUD_MODEL, "backup_provider": PAID[0],
              "backup_model": PAID[1], "fallback_policy": "none"}
    values.update(overrides)
    return config(**values)


def test_only_the_7a_first_capabilities_are_routable():
    assert ROUTABLE_CAPABILITIES == {"writing_evaluator", "writing_improver", "text_discussion"}
    with pytest.raises(AICapabilityConfigInvalid, match="cannot be routed"):
        validate_routed_policy("learner_dictionary", routed_config())


def test_with_nothing_reviewed_no_capability_can_be_routed():
    for key in ROUTABLE_CAPABILITIES:
        assert caps.require_capability(key).reviewed_primary_models == frozenset()
        with pytest.raises(AICapabilityConfigInvalid, match="reviewed primary"):
            validate_routed_policy(key, routed_config())


def test_a_fully_reviewed_chain_is_accepted(reviewed):
    reviewed()
    validate_routed_policy("writing_evaluator", routed_config())


@pytest.mark.parametrize(("overrides", "kwargs", "match"), [
    ({"model": "other-model"}, {}, "reviewed primary"),
    ({"provider": "ollama", "model": "qwen3:8b"}, {"primary": (("ollama", "qwen3:8b"),)}, "local-model"),
    ({"backup_provider": "ollama", "backup_model": "qwen3:8b"}, {"backup": (("ollama", "qwen3:8b"),)}, "local-model"),
    ({"provider": "openrouter", "model": "google/gemma-4-31b-it:free"},
     {"primary": (("openrouter", "google/gemma-4-31b-it:free"),)}, "learner text"),
    ({}, {"privacy": ()}, "privacy classification"),
    ({"backup_model": "gpt-4o"}, {}, "reviewed backup"),
    ({"backup_provider": "openai", "backup_model": "unpriced-model"}, {"backup": (("openai", "unpriced-model"),)},
     "unpriced"),
    ({}, {"cap": 0.0}, "daily spend cap above zero"),
])
def test_the_routed_policy_refuses(reviewed, overrides, kwargs, match):
    reviewed(**kwargs)
    with pytest.raises(AICapabilityConfigInvalid, match=match):
        validate_routed_policy("writing_evaluator", routed_config(**overrides))


def test_a_cap_of_zero_is_not_invalid_at_run_time(reviewed):
    reviewed(cap=0.0)
    validate_routed_policy("writing_evaluator", routed_config(), enforce_cap=False)   # the budget gate skips it


# ---- the routing switch and the legacy guard ---------------------------------------------------------------------

def test_the_switch_is_empty_by_default_and_ignores_unroutable_keys(monkeypatch):
    monkeypatch.delenv(platform.ROUTING_SWITCH, raising=False)
    assert platform.routed_capabilities() == frozenset()
    monkeypatch.setenv(platform.ROUTING_SWITCH, "writing_evaluator, learner_dictionary ,text_discussion")
    assert platform.routed_capabilities() == {"writing_evaluator", "text_discussion"}


def test_a_listed_capability_without_a_config_never_falls_back_to_legacy(monkeypatch):
    calls = []
    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    monkeypatch.setenv(platform.ROUTING_SWITCH, "writing_evaluator")
    monkeypatch.setattr(platform, "_platform_repository", Repository(None))
    monkeypatch.setattr(platform, "active_selection", lambda: calls.append("legacy") or (Provider(), "m"))
    with pytest.raises(AICapabilityNotConfigured):
        platform.generate_structured(messages=[], schema={"type": "object"}, max_output_tokens=10,
                                     capability_key="writing_evaluator")
    assert calls == []


def test_a_listed_capability_whose_config_is_not_reviewed_is_refused_before_any_call(monkeypatch):
    provider = Provider()
    monkeypatch.setenv(platform.ROUTING_SWITCH, "writing_evaluator")
    monkeypatch.setattr(platform, "_platform_repository", Repository(config()))   # openai, not a reviewed primary
    monkeypatch.setattr(platform, "providers", lambda: {"openai": provider})
    with pytest.raises(AICapabilityConfigInvalid, match="reviewed primary"):
        platform.generate_structured(messages=[], schema={"type": "object"}, max_output_tokens=10,
                                     capability_key="writing_evaluator")


class OpenRouterFree(Provider):
    id = "openrouter"


@pytest.mark.parametrize("key", ["writing_evaluator", "writing_improver", "text_discussion", None, "contextual_dictionary"])
def test_the_legacy_selection_never_sends_learner_text_to_a_free_or_logging_provider(monkeypatch, key):
    sent = []

    class Free(OpenRouterFree):
        def generate_json(self, **kwargs):
            sent.append(kwargs)
            return AIResult(data={}, provider="openrouter", model=kwargs["model"], runtime={})

    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    monkeypatch.delenv(platform.ROUTING_SWITCH, raising=False)
    monkeypatch.setattr(platform, "_platform_repository", Repository(None))
    monkeypatch.setattr(platform, "active_selection", lambda: (Free(), "google/gemma-4-31b-it:free"))
    with pytest.raises(AIProviderUnavailable, match="cannot receive learner text"):
        platform.generate_structured(messages=[], schema={"type": "object"}, max_output_tokens=10, capability_key=key)
    assert sent == []


def test_the_legacy_guard_lets_public_reference_through(monkeypatch):
    sent = []

    class Free(OpenRouterFree):
        def generate_json(self, **kwargs):
            sent.append(kwargs)
            return AIResult(data={"meaning": "x"}, provider="openrouter", model=kwargs["model"], runtime={})

    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    monkeypatch.setattr(platform, "_platform_repository", Repository(None))
    monkeypatch.setattr(platform, "active_selection", lambda: (Free(), "google/gemma-4-31b-it:free"))
    platform.generate_structured(messages=[], schema={"type": "object"}, max_output_tokens=10,
                                 capability_key="word_translation")
    assert len(sent) == 1


# ---- covered-credit coverage -------------------------------------------------------------------------------------

def test_an_ollama_cloud_call_keeps_its_cost_and_an_unknown_coverage(monkeypatch):
    repository = Repository(None)
    monkeypatch.setattr(platform, "_platform_repository", repository)
    platform._persist_operation_telemetry({"capability": "writing_evaluator", "origin": "learner",
                                           "provider": "ollama-cloud", "model": CLOUD_MODEL, "outcome": "success",
                                           "cost": {"state": "estimated", "currency": "USD", "amount": 0.001}})
    platform._persist_operation_telemetry({"capability": "writing_evaluator", "origin": "learner",
                                           "provider": "openai", "model": "gpt-4o-mini", "outcome": "success"})
    cloud, paid = repository.events
    assert cloud["cost_coverage"] == "unknown" and cloud["cost"]["amount"] == 0.001
    assert "cost_coverage" not in paid
    assert sanitize_telemetry({"outcome": "success", "capability": "x", "cost_coverage": "provider_credit"}).get(
        "cost_coverage") is None   # only the estimated vocabulary is kept


# ---- the benchmark harness ---------------------------------------------------------------------------------------

def test_the_benchmark_reports_the_five_measurements_and_never_a_verdict():
    from writing_coach.ai.model_benchmark import BenchmarkCase, compare, run_replay, score

    cases = [BenchmarkCase(f"c{i}", {"text": "t"}, {"band": "B1"}) for i in range(4)]

    def validate(data: dict[str, Any]) -> None:
        if "band" not in data:
            raise ValueError("schema")

    def grade(case, data):
        right = data["band"] == case.expect["band"]
        return (1.0 if right else 0.0), (not right)

    candidate = run_replay([
        {"case_id": "c0", "data": {"band": "B1"}, "latency_ms": 900, "cost_state": "estimated", "cost_usd": "0.001"},
        {"case_id": "c1", "data": {"band": "A2"}, "latency_ms": 1100, "cost_state": "estimated", "cost_usd": "0.001"},
        {"case_id": "c2", "data": {"nope": 1}, "latency_ms": 700, "cost_state": "unpriced"},
        {"case_id": "c3", "data": None, "latency_ms": 3000, "error": "AIProviderTimeout"},
    ])
    baseline = run_replay([{"case_id": f"c{i}", "data": {"band": "B1"}, "latency_ms": 500, "cost_state": "estimated",
                            "cost_usd": "0.004"} for i in range(4)])
    a = score("ollama-cloud/candidate", cases, candidate, validate=validate, grade=grade).as_dict()
    assert a["schema_valid_rate"] == 0.5 and a["quality_mean"] == 0.5
    assert a["critical_failure_rate"] == 0.75   # a wrong band, a schema failure, an error
    assert a["latency_ms"]["max"] == 3000
    assert a["cost_usd"] == {"total_priced": "0.002", "mean_priced": "0.001", "priced_cases": 2,
                             "unpriced_or_unknown_cases": 1, "failed_calls": 1}   # an error was never priced
    report = compare(score("cand", cases, candidate, validate=validate, grade=grade),
                     score("base", cases, baseline, validate=validate, grade=grade))
    assert report["verdict"] is None and report["difference"]["quality_mean"] == -0.5
    assert Decimal(report["candidate"]["cost_usd"]["mean_priced"]) < Decimal(report["baseline"]["cost_usd"]["mean_priced"])


# ---- the review refresh is metered under writing.review (H7-3) ------------------------------------------------------

from tests.test_d4_review_refresh import client, seed, stack  # noqa: E402,F401
from tests.test_quota_gate import _isolated, enforced_runtime  # noqa: E402,F401


def test_a_refresh_that_calls_remote_ai_is_one_writing_review(client, stack):  # noqa: F811
    repository = enforced_runtime()
    essay_id, _values = seed(stack, learning="zh", support="vi")
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.status_code == 200 and answer.json()["status"] == "refreshed"
    assert repository.calls.count("reserve") == 1 and "dispatch" in repository.calls and "settle:1" in repository.calls


def test_a_refresh_that_cannot_be_earned_settles_zero(client, stack):  # noqa: F811
    from writing_coach.ai.base import AIProviderError

    repository = enforced_runtime()
    client.behaviour["raise"] = AIProviderError("provider failed")
    essay_id, _values = seed(stack, learning="zh", support="vi")
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.json()["status"] == "unavailable"
    assert "settle:0" in repository.calls and "settle:1" not in repository.calls


def test_a_refresh_with_an_exhausted_meter_is_refused_before_any_provider_call(client, stack):  # noqa: F811
    from writing_coach.product import quota

    repository = enforced_runtime()
    for index in range(2):   # Free: 2 reviews a month
        with quota.admit("writing.review", request_digest=f"spend-{index}") as ticket:
            ticket.dispatch("p")
    essay_id, _values = seed(stack, learning="zh", support="vi")
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.status_code == 429 and answer.json()["detail"]["category"] == "quota_exhausted"
    assert client.calls == []
    assert repository.calls.count("reserve") == 3


def test_a_current_review_is_not_admitted(client, stack):  # noqa: F811
    from tests.test_d4_review_refresh import V27

    repository = enforced_runtime()
    essay_id, _values = seed(stack, learning="zh", support="vi", contract=V27)
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.json()["status"] == "current" and "reserve" not in repository.calls and client.calls == []


def test_a_routed_but_unconfigured_evaluator_or_improver_is_503_never_500_or_a_fallback(monkeypatch):
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    import app as app_module

    def unconfigured(*_a, **_k):
        raise AICapabilityNotConfigured("writing_evaluator has no explicit configuration.")

    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", True)   # even with the heuristic allowed, no fallback
    monkeypatch.setattr(app_module, "evaluate_with_ai", unconfigured)
    with pytest.raises(HTTPException) as refused:
        app_module.evaluate(app_module.EssayIn(text="Hello there.", prompt="p"))
    assert refused.value.status_code == 503 and refused.value.detail["category"] == "evaluation_unavailable"
    monkeypatch.setattr(app_module, "improve_with_ai", unconfigured)
    with TestClient(app_module.app) as http:
        answer = http.post("/api/improve", json={"text": "I goes to school every days and I like it very much.",
                                                 "mode": "polish"})
    assert answer.status_code == 503


def test_the_reading_summary_stays_legacy_when_text_discussion_is_routed(monkeypatch):
    """It reuses the `text_discussion` key, but its shared cache keeps it out of 7A-first (design F-2/F-4)."""
    from writing_coach import reading_summary

    sent = []

    class Legacy(Provider):
        def generate_json(self, **kwargs):
            sent.append(kwargs["model"])
            return AIResult(data={"bullets": ["a"]}, provider="openai", model=kwargs["model"], runtime={})

    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    monkeypatch.setenv(platform.ROUTING_SWITCH, "text_discussion")
    monkeypatch.setattr(platform, "_platform_repository", Repository(None))   # a routed call would be unconfigured
    monkeypatch.setattr(platform, "active_selection", lambda: (Legacy(), "legacy-model"))
    assert reading_summary._platform_generate(messages=[], schema={"type": "object"}, max_output_tokens=10) == {
        "bullets": ["a"]}
    assert sent == ["legacy-model"]
    with pytest.raises(AICapabilityNotConfigured):   # the discussion itself is routed
        platform.generate_structured(messages=[], schema={"type": "object"}, max_output_tokens=10,
                                     capability_key="text_discussion")


# ---- independent pre-review fixes ------------------------------------------------------------------------------------

class CloudFake:
    id = "ollama-cloud"
    name = "Ollama Cloud"
    configured = True
    timeout = 120

    def __init__(self, answers):
        self.answers, self.calls = list(answers), 0

    def generate_json_once(self, **kwargs):
        self.calls += 1
        return AIResult(data=dict(self.answers.pop(0)), provider=self.id, model=kwargs["model"],
                        runtime={"prompt_tokens": 10, "completion_tokens": 5})

    generate_json = generate_json_once


class PaidFake(CloudFake):
    id = "openai"
    name = "OpenAI"


class LedgerRepository(Repository):
    def ai_spend_since_for_capability(self, capability, since):
        return 0.0, 0


def routed_world(monkeypatch, reviewed, *, cap, primary_answers, backup_answers=()):
    reviewed(cap=cap)
    cloud, paid = CloudFake(primary_answers), PaidFake(backup_answers)
    monkeypatch.setenv(platform.ROUTING_SWITCH, "writing_evaluator")
    monkeypatch.setattr(platform, "_platform_repository", LedgerRepository(routed_config()))
    monkeypatch.setattr(platform, "providers", lambda: {"ollama-cloud": cloud, "openai": paid})
    from writing_coach.ai import spend_gate

    spend_gate.reset()
    return cloud, paid


def ask(validate=None):
    return platform.generate_structured(messages=[], schema={"type": "object"}, max_output_tokens=10,
                                        capability_key="writing_evaluator", validate=validate)


def test_a_routed_primary_answers_even_with_the_backup_cap_at_zero(monkeypatch, reviewed):
    cloud, paid = routed_world(monkeypatch, reviewed, cap=0.0, primary_answers=[{"ok": True}])
    result = ask()
    assert result.provider == "ollama-cloud" and cloud.calls == 1 and paid.calls == 0


def test_at_cap_zero_an_invalid_primary_never_reaches_the_paid_backup(monkeypatch, reviewed):
    from writing_coach.ai.base import AIOutputInvalid, AIProviderError

    def validate(data):
        if not data.get("ok"):
            raise AIOutputInvalid("bad")

    cloud, paid = routed_world(monkeypatch, reviewed, cap=0.0, primary_answers=[{"ok": False}, {"ok": False}],
                               backup_answers=[{"ok": True}])
    with pytest.raises(AIProviderError):
        ask(validate)
    assert paid.calls == 0   # the backup is skipped by its cap


def test_with_a_backup_cap_the_reviewed_backup_answers_after_an_invalid_primary(monkeypatch, reviewed):
    from writing_coach.ai.base import AIOutputInvalid

    def validate(data):
        if not data.get("ok"):
            raise AIOutputInvalid("bad")

    cloud, paid = routed_world(monkeypatch, reviewed, cap=1.0, primary_answers=[{"ok": False}, {"ok": False}],
                               backup_answers=[{"ok": True}])
    result = ask(validate)
    assert result.provider == "openai" and paid.calls == 1 and cloud.calls == 1   # no invalid re-ask by default


def test_ollama_cloud_discovery_authenticates_so_a_wrong_key_fails_the_admin_test(monkeypatch):
    from writing_coach.ai.base import AIProviderError

    seen = {}

    class Response:
        def __init__(self, status):
            self.status_code = status

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests

                raise requests.HTTPError(response=self)

        def json(self):
            return {"models": [{"name": CLOUD_MODEL}, {"name": "unlisted"}]}

    def get(url, headers, timeout):
        seen.update(url=url, headers=headers)
        return Response(401 if headers["Authorization"] == "Bearer wrong" else 200)

    monkeypatch.setattr(prov.requests, "get", get)
    good = prov.OllamaCloudProvider({"api_key": "right", "models": [CLOUD_MODEL, "listed-not-published"]})
    assert good.discover_models_live() == [CLOUD_MODEL] and seen["url"] == "https://ollama.com/api/tags"
    assert good.api_key == "right"
    with pytest.raises(AIProviderError):
        prov.OllamaCloudProvider({"api_key": "wrong", "models": [CLOUD_MODEL]}).discover_models_live()
    monkeypatch.setenv("OLLAMA_CLOUD_MODELS", "env-model")
    assert prov.OllamaCloudProvider({"api_key": "k", "models": []}).list_models() == ["env-model"]


def test_a_refresh_is_403_before_any_stored_answer_when_the_plan_disables_review(client, stack):  # noqa: F811
    from tests.test_funding_gate import _disable_review_on_free

    enforced_runtime()
    _disable_review_on_free()
    essay_id, _values = seed(stack, learning="zh", support="vi")
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.status_code == 403 and answer.json()["detail"]["category"] == "feature_not_in_plan"
    assert client.calls == []
