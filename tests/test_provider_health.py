"""Provider health and the router's circuit breaker (PR BZ, P0 2026-10-20).

On 2026-10-19 every Gemini call on :8000 answered HTTP 429 "Your project has exceeded its monthly spending cap" and
nobody knew until a learner saw "Orena is busy". These tests hold: the failure classes (the real spend-cap text and an
ordinary per-minute 429 that must stay a rate limit), the alert thresholds, the breaker that stands a provider down and
sends requests to the configured backup, the switch telemetry, the D-104 guard at switch time, the admin route's guard,
and that no prompt, key or learner text reaches any of it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import writing_coach.ai.platform as platform
from tests.policy_support import MemoryPolicyStore, installed
from tests.test_ai_router import GEMMA, LAMP, STANDBY, env  # noqa: F401 - `env` is a fixture
from writing_coach import policies
from writing_coach.ai import health_signal, routing
from writing_coach.ai.base import AIOutputInvalid, AIProviderError, AIProviderTimeout, sanitize_telemetry
from writing_coach.ai.capabilities import require_capability
from writing_coach.ai.config import learner_text_refused
from writing_coach.ai.health_signal import classify_failure, failure_class_of, provider_health
from writing_coach.ai.router import route
from writing_coach.ai.routing import ProviderHealth, ProviderTarget, run_chain

# The provider's own words, as Gemini's OpenAI-compatible endpoint sent them on :8000 (2026-10-19) and as it sends an
# ordinary free-tier per-minute limit. The second also says "quota" and "billing": it must stay a rate limit.
GEMINI_SPEND_CAP = ("Your project has exceeded its monthly spending cap. Please go to AI Studio at "
                    "https://ai.studio/spend to manage your project spend cap.")
GEMINI_PER_MINUTE = ("You exceeded your current quota, please check your plan and billing details. For more information "
                     "on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. Quota exceeded for "
                     "metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 15. "
                     "Please retry in 41.6s.")
SECRET_PROMPT = "my private essay about my landlord"
NOW = datetime(2026, 10, 19, 23, 30, tzinfo=UTC)


def http_error(status: int, detail: str = "", provider: str = "Gemini") -> AIProviderError:
    error = AIProviderError(f"{provider} returned HTTP {status}. {detail}".strip())
    error.status_code = status
    return error


# ===================================================================================================== classification ==

@pytest.mark.parametrize(("status", "text", "expected"), [
    (429, GEMINI_SPEND_CAP, "spend_cap"),
    (429, GEMINI_PER_MINUTE, "rate_limit"),
    (429, "Rate limit reached for model in organization on tokens per min (TPM)", "rate_limit"),
    (429, "insufficient_quota", "spend_cap"),
    (429, "Your organization has reached its spend limit", "spend_cap"),
    (402, "Payment required", "spend_cap"),
    (401, "API key not valid. Please pass a valid API key.", "auth"),
    (403, "Permission denied on resource project", "auth"),
    (400, "API key not valid. Please pass a valid API key.", "auth"),
    (400, "Invalid JSON payload received. Unknown name \"foo\"", "schema"),
    (422, "response_format is invalid", "schema"),
    (404, "models/gemini-1.0 is not found", "unconfigured"),
    (500, "Internal error", "server"),
    (503, "The model is overloaded", "server"),
])
def test_each_http_failure_has_its_class(status, text, expected):
    assert classify_failure(status=status, text=text) == expected
    assert failure_class_of(http_error(status, text)) == expected


def test_the_classes_of_errors_without_a_status():
    assert failure_class_of(AIProviderTimeout("Gemini timed out.")) == "timeout"
    assert failure_class_of(TimeoutError()) == "timeout"
    from writing_coach.ai.base import AICapabilityDisabled, AIProviderNotConfigured, AIProviderResponseInvalid

    assert failure_class_of(AIProviderNotConfigured("Gemini is not configured on the server.")) == "unconfigured"
    assert failure_class_of(AICapabilityDisabled("off")) == "unconfigured"
    assert failure_class_of(AIProviderResponseInvalid("AI provider returned an invalid response.")) == "schema"
    assert failure_class_of(AIOutputInvalid("bad word")) == "not_counted"
    assert failure_class_of(None, error_class="client_abandoned") == "not_counted"


def test_the_provider_adapter_stamps_the_class_from_the_body_and_its_error_code():
    from writing_coach.ai.providers import _http_failure_class

    class Response:
        def __init__(self, status, body):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

    # Gemini wraps its error in a list; OpenAI's insufficient_quota carries the per-minute words but its own code.
    gemini = Response(429, [{"error": {"code": 429, "message": GEMINI_SPEND_CAP, "status": "RESOURCE_EXHAUSTED"}}])
    assert _http_failure_class(gemini, GEMINI_SPEND_CAP) == "spend_cap"
    per_minute = Response(429, [{"error": {"code": 429, "message": GEMINI_PER_MINUTE, "status": "RESOURCE_EXHAUSTED"}}])
    assert _http_failure_class(per_minute, GEMINI_PER_MINUTE) == "rate_limit"
    openai = Response(429, {"error": {"message": "You exceeded your current quota, please check your plan and billing "
                                                "details.", "type": "insufficient_quota", "code": "insufficient_quota"}})
    assert _http_failure_class(openai, "You exceeded your current quota") == "spend_cap"
    assert _http_failure_class(Response(401, ValueError), "") == "auth"


def test_the_stored_row_keeps_only_the_class_never_the_message():
    row = sanitize_telemetry({"capability": "learner_dictionary", "origin": "learner", "provider": "gemini",
                              "outcome": "failure", "error_class": "provider_error", "failure_class": "spend_cap",
                              "message": GEMINI_SPEND_CAP, "prompt": SECRET_PROMPT,
                              "provider_switch": {"from": "gemini", "to": "groq", "reason": "spend_cap",
                                                  "trigger": "down", "text": SECRET_PROMPT}})
    assert row["failure_class"] == "spend_cap"
    assert row["provider_switch"] == {"from": "gemini", "to": "groq", "reason": "spend_cap", "trigger": "down"}
    text = json.dumps(row)
    assert SECRET_PROMPT not in text and "spending cap" not in text
    assert "failure_class" not in sanitize_telemetry({"capability": "x", "outcome": "failure", "failure_class": "free text"})
    assert sanitize_telemetry({"capability": "x", "outcome": "failure",
                               "provider_switch": {"from": "https://x?key=1", "to": "groq"}}).get("provider_switch") is None


# ========================================================================================================= thresholds ==

def event(minutes_ago: float, outcome: str = "failure", cls: str | None = "rate_limit", provider: str = "gemini",
          capability: str = "agent_turn_fast", **extra: Any) -> dict[str, Any]:
    row = {"capability": capability, "origin": "learner", "provider": provider, "outcome": outcome,
           "created_at": (NOW - timedelta(minutes=minutes_ago)).isoformat()}
    if outcome == "failure" and cls:
        row["failure_class"] = cls
    row.update(extra)
    return row


LIMITS = {"window_minutes": 10, "consecutive": 3, "window_failures": 3}


def report(events):
    return provider_health(events, now=NOW, limits=LIMITS)


def test_two_rate_limits_are_degraded_not_an_alert():
    result = report([event(1), event(2), event(3, "success", None)])
    assert result["status"] == "ok" and result["alerts"] == []
    assert result["providers"][0]["status"] == "degraded" and result["providers"][0]["failed"] == 2


def test_three_failures_in_a_row_alert_at_medium():
    result = report([event(1), event(2), event(3), event(4, "success", None)])
    assert result["severity"] == "medium" and result["alerts"][0]["consecutive_failures"] == 3
    assert result["alerts"][0]["failure_class"] == "rate_limit"


def test_three_failures_in_the_window_alert_even_with_successes_between():
    result = report([event(1), event(2, "success", None), event(3, cls="server"), event(4, "success", None),
                     event(5, cls="timeout")])
    assert result["severity"] == "medium" and result["alerts"][0]["failed"] == 3
    assert result["alerts"][0]["consecutive_failures"] == 1


def test_a_spending_cap_alerts_at_once_and_high():
    result = report([event(0.5, cls="spend_cap", capability="learner_dictionary")])
    assert result["status"] == "alert" and result["severity"] == "high"
    alert = result["alerts"][0]
    assert (alert["provider"], alert["failure_class"], alert["capabilities"]) == ("gemini", "spend_cap", ["learner_dictionary"])


def test_a_rejected_key_alerts_at_once_and_a_later_success_clears_it():
    assert report([event(1, cls="auth")])["severity"] == "high"
    assert report([event(0.5, "success", None), event(1, cls="auth")])["alerts"] == []


def test_the_window_skips_and_the_rows_that_are_not_provider_failures():
    old = [event(11), event(12), event(13)]
    assert report(old)["providers"] == []
    ignored = [
        event(1, origin="operator_test"), event(1, origin="configuration"),
        event(2, cls="not_counted"), event(2, cls=None, error_class="budget_skipped"),
        event(3, chain_summary=True), event(3, cls=None, error_class="output_invalid"),
    ]
    assert report(ignored)["providers"] == []


def test_a_row_recorded_before_the_class_is_classified_from_its_closed_fields():
    legacy = [event(1, cls=None, http_status_class="429"), event(2, cls=None, http_status_class="5xx"),
              event(3, cls=None, error_class="provider_timeout")]
    assert report(legacy)["providers"][0]["by_class"] == {"rate_limit": 1, "server": 1, "timeout": 1}


def test_failing_since_reaches_past_the_window_and_per_capability_counts_are_kept():
    rows = [event(1, cls="spend_cap"), event(30, cls="spend_cap", capability="learner_dictionary"),
            event(40, "success", None)]
    result = report(rows)
    assert result["alerts"][0]["failing_since"] == (NOW - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert [cap["capability"] for cap in result["providers"][0]["capabilities"]] == ["agent_turn_fast"]


def test_the_thresholds_are_admin_policies():
    with installed(MemoryPolicyStore()):
        assert health_signal.thresholds() == {"window_minutes": 10, "consecutive": 3, "window_failures": 3}
        policies.save({"set": {"ai.health_window_failures": 5, "ai.health_window_minutes": 30}},
                      updated_by="admin@x.test", actor="admin-sub")
        assert health_signal.thresholds() == {"window_minutes": 30, "consecutive": 3, "window_failures": 5}
    for key in ("ai.health_window_minutes", "ai.health_consecutive_failures", "ai.health_window_failures",
                "ai.breaker_hard_cooldown_minutes", "ai.breaker_rate_limit_failures",
                "ai.breaker_rate_limit_cooldown_seconds"):
        assert policies.BY_KEY[key].group == "health"


# ======================================================================================================= output / CLI ==

def test_nothing_a_learner_wrote_or_a_key_reaches_the_report_or_the_line():
    rows = [event(1, cls="spend_cap", prompt=SECRET_PROMPT, text=SECRET_PROMPT, api_key="AIzaSySecret",
                  message=GEMINI_SPEND_CAP)]
    result = report(rows)
    result["switches"] = health_signal.switch_history(rows)
    result["down"] = health_signal.down_providers(result, result["switches"])
    text = json.dumps(result) + health_signal.health_line(result)
    for secret in (SECRET_PROMPT, "AIzaSySecret", "spending cap. Please"):
        assert secret not in text


def test_the_health_line_says_who_is_down_why_and_since_when():
    rows = [event(1, cls="spend_cap", capability="learner_dictionary"), event(2, cls="spend_cap")]
    result = report(rows)
    result["down"] = health_signal.down_providers(result, [])
    line = health_signal.health_line(result)
    assert line.startswith("status=alert severity=high window_min=10 gemini:spend_cap(high) failed=2 consecutive=2 ")
    assert "since=2026-10-19T23:28:00Z" in line and "caps=agent_turn_fast,learner_dictionary" in line
    assert "[spending cap reached]" in line
    assert health_signal.health_line(report([event(1, "success", None)])) == "status=ok calls=1 window_min=10"
    assert health_signal.health_line(health_signal.unavailable_report(NOW)) == "status=unknown telemetry unreadable"


def test_the_cli_prints_one_json_line_and_unknown_without_a_database(monkeypatch, capsys):
    monkeypatch.delenv("POSTGRES_RUNTIME_URL", raising=False)
    assert health_signal.main([]) == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    parsed = json.loads(out[0])
    assert parsed["available"] is False and parsed["status"] == "unknown" and parsed["version"] == 1
    assert parsed["line"] == "status=unknown telemetry unreadable"


def test_the_report_from_a_repository_adds_the_switches_and_who_is_down():
    rows = [event(1, cls="spend_cap", capability="learner_dictionary"),
            event(0.5, "success", None, provider="groq", capability="learner_dictionary",
                  provider_switch={"from": "gemini", "to": "groq", "reason": "spend_cap", "trigger": "down"}),
            event(0.4, cls="spend_cap", capability="agent_turn_fast")]

    class Repo:
        def list_ai_operation_events(self, limit):
            assert limit == health_signal.SAMPLE_LIMIT
            return rows

    with installed(MemoryPolicyStore()):
        result = health_signal.report_from_repository(Repo(), now=NOW)
    assert result["switches"][0] == {"at": "2026-10-19T23:29:30Z", "capability": "learner_dictionary", "from": "gemini",
                                     "to": "groq", "reason": "spend_cap", "trigger": "down", "answered": True}
    down = result["down"][0]
    assert (down["provider"], down["reason"], down["severity"]) == ("gemini", "spend_cap", "high")
    assert down["on_backup"] == ["learner_dictionary"] and down["without_backup"] == ["agent_turn_fast"]

    class Broken:
        def list_ai_operation_events(self, limit):
            raise RuntimeError("database down")

    assert health_signal.report_from_repository(Broken(), now=NOW)["status"] == "unknown"


# ===================================================================================================== circuit breaker ==

class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def fixed(values):
    return lambda key, default: values.get(key, default)


def test_a_spending_cap_stands_the_provider_down_for_the_policy_then_one_probe_goes_through():
    clock = Clock()
    health = ProviderHealth(clock=clock, policy=fixed({"ai.breaker_hard_cooldown_minutes": 30}))
    health.record_failure("gemini", "spend_cap")
    assert health.is_available("gemini") is False
    state = health.snapshot()["gemini"]
    assert state["reason"] == "spend_cap" and state["cooling_down"] and 1790 <= state["seconds_remaining"] <= 1800
    clock.now += 29 * 60
    assert health.is_available("gemini") is False
    clock.now += 61
    assert health.is_available("gemini") is True          # half open: one probe
    health.record_failure("gemini", "spend_cap")            # still capped: down again for the whole cooldown
    assert health.is_available("gemini") is False and health.down_reason("gemini") == "spend_cap"
    clock.now += 30 * 60 + 1
    assert health.is_available("gemini") is True
    health.record_success("gemini")
    assert health.snapshot() == {} and health.down_reason("gemini") is None


def test_a_rejected_key_follows_the_hard_cooldown_policy():
    clock = Clock()
    health = ProviderHealth(clock=clock, policy=fixed({"ai.breaker_hard_cooldown_minutes": 5}))
    health.record_failure("gemini", "auth")
    clock.now += 5 * 60 + 1
    assert health.is_available("gemini") is True


def test_repeated_rate_limits_stand_it_down_for_the_shorter_time():
    clock = Clock()
    health = ProviderHealth(clock=clock, policy=fixed({"ai.breaker_rate_limit_failures": 2,
                                                       "ai.breaker_rate_limit_cooldown_seconds": 60}))
    health.record_failure("gemini", "rate_limit")
    assert health.is_available("gemini") is True
    health.record_failure("gemini", "rate_limit")
    assert health.is_available("gemini") is False and health.down_reason("gemini") == "rate_limit"
    clock.now += 61
    assert health.is_available("gemini") is True


def test_the_breaker_policies_default_to_thirty_minutes_and_a_short_rate_limit_pause():
    assert policies.default("ai.breaker_hard_cooldown_minutes") == 30
    assert policies.default("ai.breaker_rate_limit_cooldown_seconds") < 30 * 60


def test_while_the_primary_is_down_the_chain_goes_straight_to_the_backup():
    health = ProviderHealth(clock=Clock())
    asked: list[str] = []

    def attempt(target):
        asked.append(target.provider)
        if target.provider == "gemini":
            raise http_error(429, GEMINI_SPEND_CAP)
        return "answered"

    chain = [ProviderTarget("gemini", "gemini-3.5-flash-lite"), ProviderTarget("groq", "openai/gpt-oss-120b")]
    first = run_chain(chain, attempt, health=health)
    assert first.attempts[0].failure_class == "spend_cap" and asked == ["gemini", "groq"]
    second = run_chain(chain, attempt, health=health)
    assert asked == ["gemini", "groq", "groq"], "the provider that is down is not asked again"
    assert (second.attempts[0].outcome, second.attempts[0].failure_class) == ("skipped_unhealthy", "spend_cap")
    assert platform.provider_switch(second.attempts, "groq") == {"from": "gemini", "to": "groq", "reason": "spend_cap",
                                                                 "trigger": "down"}
    assert platform.provider_switch(first.attempts, "groq")["trigger"] == "failed"
    assert platform.provider_switch(first.attempts[1:], "groq") is None


def test_a_switch_through_the_router_is_recorded_without_a_word(env):  # noqa: F811 - the fixture
    env.fake.script = {GEMMA: [http_error(429, GEMINI_PER_MINUTE, "OpenRouter")]}
    route("word_translation", LAMP)
    answered = [op for op in env.repo.operations if op["outcome"] == "success"][-1]
    assert answered["model"] == STANDBY
    assert answered["provider_switch"] == {"from": "openrouter", "to": "openrouter", "reason": "rate_limit",
                                           "trigger": "failed"}
    failed = [op for op in env.repo.operations if op["outcome"] == "failure"]
    assert failed[0]["failure_class"] == "rate_limit"
    assert "lamp" not in json.dumps(env.repo.operations)


def test_a_spend_cap_stands_that_model_down_and_the_next_request_goes_straight_to_the_standby(env):  # noqa: F811
    # A spending cap is held per model: an OpenRouter credit balance (402) leaves its free models answering, and a
    # project cap (Gemini) stands each model down at its own first failure.
    env.fake.script = {GEMMA: [http_error(429, "Your organization has reached its spend limit", "OpenRouter")]}
    route("word_translation", LAMP)
    assert routing.provider_health.down_reason("openrouter", GEMMA) == "spend_cap"
    assert routing.provider_health.down_reason("openrouter") is None
    route("word_translation", {**LAMP, "text": "chair"})
    assert [call["model"] for call in env.fake.calls] == [GEMMA, STANDBY, STANDBY], "the capped model is not asked"
    answered = [op for op in env.repo.operations if op["outcome"] == "success"]
    assert [op["provider_switch"]["trigger"] for op in answered] == ["failed", "down"]
    assert answered[-1]["provider_switch"]["reason"] == "spend_cap"
    skipped = [op for op in env.repo.operations if op["outcome"] == "failure"][-1]
    assert skipped["failure_class"] == "not_counted"
    snapshot = routing.provider_health.snapshot()[f"openrouter:{GEMMA}"]
    assert (snapshot["provider"], snapshot["reason"], snapshot["cooling_down"]) == ("openrouter", "spend_cap", True)
    down = health_signal.down_providers({"alerts": []}, [], routing.provider_health.snapshot())
    assert down[0]["provider"] == "openrouter" and down[0]["reason"] == "spend_cap"


# ================================================================================================ D-104 at switch time ==

def test_a_learner_text_capability_refuses_a_free_or_prompt_logging_backup_at_switch_time():
    learner_text = require_capability("writing_evaluator")
    assert learner_text.input_class == "learner_text"
    assert learner_text_refused(learner_text, "openrouter", "google/gemma-4-31b-it:free") is True
    assert learner_text_refused(learner_text, "groq", "llama-3.1-8b-instant") is True   # a zero-rate free-plan model
    assert learner_text_refused(learner_text, "no-such-provider", "m") is True
    assert learner_text_refused(learner_text, "gemini", "gemini-3.5-flash-lite") is False
    public = require_capability("word_translation")
    assert learner_text_refused(public, "openrouter", "google/gemma-4-31b-it:free") is False


def test_the_privacy_gate_skips_a_refused_rung_before_it_is_asked():
    learner_text = require_capability("writing_evaluator")
    admit = platform._privacy_gate(learner_text, None)
    assert admit(ProviderTarget("openrouter", "google/gemma-4-31b-it:free")) == "privacy"
    assert admit(ProviderTarget("gemini", "gemini-3.5-flash-lite")) is None
    health = ProviderHealth(clock=Clock())
    health.record_failure("gemini", "spend_cap")
    asked: list[str] = []
    chain = [ProviderTarget("gemini", "gemini-3.5-flash-lite"), ProviderTarget("openrouter", "google/gemma-4-31b-it:free")]
    with pytest.raises(routing.AllProvidersUnavailable) as caught:
        run_chain(chain, lambda target: asked.append(target.provider), health=health, admit=admit)
    assert asked == [], "nothing is sent: the caller answers with its gentle error or deterministic rung"
    assert [(a.outcome, a.reason) for a in caught.value.attempts] == [("skipped_unhealthy", "cooling_down"),
                                                                       ("skipped_budget", "privacy")]


# ========================================================================================================== admin API ==

def test_the_health_route_is_behind_the_admin_guard(monkeypatch):
    rows = [event(1, cls="spend_cap")]

    class Repo:
        def list_ai_operation_events(self, limit):
            return [{**row, "created_at": datetime.now(UTC).isoformat()} for row in rows]

    monkeypatch.setattr(platform, "_platform_repository", Repo())
    app = FastAPI()
    app.include_router(platform.router)

    def refuse(request):
        raise HTTPException(403, "Platform administrator access is required.")

    monkeypatch.setattr(platform, "_admin_guard", refuse)
    assert TestClient(app).get("/api/admin/ai/health").status_code == 403
    monkeypatch.setattr(platform, "_admin_guard", lambda request: {"google_sub": "admin"})
    routing.provider_health.reset()
    try:
        answer = TestClient(app).get("/api/admin/ai/health")
    finally:
        routing.provider_health.reset()
    assert answer.status_code == 200 and answer.headers["cache-control"] == "no-store"
    body = answer.json()
    assert body["severity"] == "high" and body["down"][0]["provider"] == "gemini" and body["breaker"] == []
