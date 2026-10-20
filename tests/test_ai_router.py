"""The AI Cost Router, slice 1 (D-195): `route("word_translation", ...)` over the v1 primary + standby configuration.

Fake providers only: no network, no key, no live call. The two pool entries are both OpenRouter ":free" models, as
they are configured in production, so the tests exercise the same-provider cooldown too.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

import writing_coach.ai.platform as platform
from writing_coach.ai import routing
from writing_coach.ai.base import (
    AICapabilityConfigInvalid,
    AICapabilityDisabled,
    AICapabilityNotConfigured,
    AIProviderError,
    AIProviderTimeout,
    AIProviderUnavailable,
    AIResult,
)
from writing_coach.ai.config import CapabilityConfig
from writing_coach.ai.router import RouterInputInvalid, route
from writing_coach.ai.router import router as router_module
from writing_coach.ai.routing import AllProvidersUnavailable
from writing_coach.persistence.platform_repository import CapabilityConfigRecord

GEMMA = "google/gemma-4-31b-it:free"
STANDBY = "google/gemma-4-26b-a4b-it:free"
LAMP = {"text": "lamp", "source_language": "en", "target_language": "vi"}


def http_error(status: int) -> AIProviderError:
    error = AIProviderError(f"HTTP {status}")
    error.status_code = status
    return error


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class Repository:
    def __init__(self, config: CapabilityConfig | None) -> None:
        self.config = config
        self.operations: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    def initialize(self) -> None:
        pass

    def get_capability_config(self, key: str) -> CapabilityConfigRecord | None:
        return CapabilityConfigRecord(key, self.config) if self.config else None

    def record_ai_operation(self, telemetry: dict[str, Any]) -> None:
        self.operations.append(telemetry)

    def record_admin_event(self, action: str, *, actor: str, entity_type: str = "", entity_id: str = "",
                           payload: dict | None = None) -> None:
        self.events.append({"action": action, "actor": actor, "entity_id": entity_id, "payload": payload})


class Fake:
    """Scripted OpenRouter: per model, a queue of answers / exceptions; the default answers cleanly."""

    id = "openrouter"
    name = "OpenRouter"
    configured = True

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.script: dict[str, list[Any]] = {}
        self.default = {GEMMA: {"meaning": "đèn"}, STANDBY: {"meaning": "cái đèn"}}
        self.on_call = None

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        self.calls.append(kwargs)
        if self.on_call:
            self.on_call(kwargs)
        queue = self.script.get(kwargs["model"])
        item = queue.pop(0) if queue else self.default[kwargs["model"]]
        if isinstance(item, BaseException):
            raise item
        return AIResult(data=dict(item), provider=self.id, model=kwargs["model"],
                        runtime={"prompt_tokens": 40, "completion_tokens": 4, "total_tokens": 44})

    generate_json = generate_json_once

    def models(self) -> list[str]:
        return [call["model"] for call in self.calls]


def config(**overrides: Any) -> CapabilityConfig:
    values = {"enabled": True, "provider": "openrouter", "model": GEMMA, "backup_provider": "openrouter",
              "backup_model": STANDBY, "temperature": 0.0, "fallback_policy": "none"}
    values.update(overrides)
    return CapabilityConfig(**values)


@pytest.fixture
def env(monkeypatch):
    clock = Clock()
    repository = Repository(config())
    provider = Fake()
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "providers", lambda: {"openrouter": provider})
    monkeypatch.setattr(routing, "monotonic", clock)
    monkeypatch.setattr(router_module, "_clock", clock)
    monkeypatch.setattr(router_module, "CONFIG_TTL_SECONDS", 0.0)
    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")  # the router does not depend on the learner runtime mode
    routing.provider_health.reset()
    router_module.reset_state()
    yield type("Env", (), {"clock": clock, "repo": repository, "fake": provider})
    routing.provider_health.reset()
    router_module.reset_state()


def word(text: str, source="en", target="vi") -> dict[str, str]:
    return {"text": text, "source_language": source, "target_language": target}


# --- the happy path ---------------------------------------------------------------------------------------------


def test_a_miss_asks_the_primary_once_and_returns_the_validated_meaning(env) -> None:
    result = route("word_translation", LAMP)
    assert result.output == {"meaning": "đèn"} and result.source == "model"
    assert env.fake.models() == [GEMMA]
    assert (result.provenance["provider"], result.provenance["model"], result.provenance["tier"]) == ("openrouter", GEMMA, "free")
    assert result.provenance["prompt_version"] == "1"


def test_the_request_sends_the_word_as_data_with_the_contract_limits(env) -> None:
    route("word_translation", LAMP)
    call = env.fake.calls[0]
    assert call["max_output_tokens"] == 120 and call["temperature"] == 0.0
    assert 0 < call["timeout"] <= 2.5
    system, user = call["messages"][0], call["messages"][-1]
    assert "lamp" not in system["content"]
    assert json.loads(user["content"])["text"] == "lamp"
    assert call["schema"]["required"] == ["meaning"]


def test_the_capability_runs_whatever_the_learner_runtime_mode_is(env, monkeypatch) -> None:
    monkeypatch.setattr(platform, "active_selection", lambda: pytest.fail("legacy routing used"))
    assert route("word_translation", LAMP).output == {"meaning": "đèn"}


# --- the cache -------------------------------------------------------------------------------------------------


def test_a_second_request_is_a_cache_hit_with_no_provider_call(env) -> None:
    first = route("word_translation", LAMP)
    second = route("word_translation", {**LAMP, "text": "  lamp "})
    assert second.output == first.output and second.source == "cache"
    assert len(env.fake.calls) == 1


def test_changing_the_model_does_not_pay_again_for_the_same_request(env) -> None:
    route("word_translation", LAMP)
    env.repo.config = config(model=STANDBY, backup_provider=None, backup_model=None)  # the operator swapped the model
    again = route("word_translation", LAMP)
    assert again.source == "cache" and again.output == {"meaning": "đèn"}  # the earlier model's answer, not a new call
    assert env.fake.models() == [GEMMA]


def test_other_languages_and_words_are_other_keys(env) -> None:
    env.fake.script = {GEMMA: [{"meaning": "đèn"}, {"meaning": "灯"}]}
    route("word_translation", LAMP)
    route("word_translation", word("lamp", target="zh"))
    route("word_translation", word("lamp", target="vi", source="en"))
    assert len(env.fake.calls) == 2


def test_a_cache_entry_expires_with_its_ttl(env) -> None:
    route("word_translation", LAMP)
    env.clock.now += 180 * 24 * 3600 + 1
    assert route("word_translation", LAMP).source == "model"
    assert len(env.fake.calls) == 2


def test_two_requests_for_one_word_at_once_make_one_call(env) -> None:
    entered, release = threading.Event(), threading.Event()

    def block(_kwargs):
        entered.set()
        release.wait(5)

    env.fake.on_call = block
    results: list[Any] = []
    first = threading.Thread(target=lambda: results.append(route("word_translation", LAMP)))
    first.start()
    assert entered.wait(5)
    second = threading.Thread(target=lambda: results.append(route("word_translation", LAMP)))
    second.start()
    time.sleep(0.2)  # the second request is waiting on the first's flight
    release.set()
    first.join(5)
    second.join(5)
    assert len(env.fake.calls) == 1
    assert [r.output for r in results] == [{"meaning": "đèn"}, {"meaning": "đèn"}]


def test_everything_down_is_remembered_for_about_a_minute(env) -> None:
    env.fake.script = {GEMMA: [http_error(503)], STANDBY: [http_error(503)]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert len(env.fake.calls) == 2
    with pytest.raises(AllProvidersUnavailable):
        route("word_translation", LAMP)
    assert len(env.fake.calls) == 2  # negative cache: no new calls
    env.clock.now += 61
    assert route("word_translation", LAMP).source == "model"
    assert len(env.fake.calls) == 3


def test_a_terminal_failure_is_not_remembered(env) -> None:
    env.fake.script = {GEMMA: [AICapabilityConfigInvalid("bad")]}
    with pytest.raises(AICapabilityConfigInvalid):
        route("word_translation", LAMP)
    assert route("word_translation", LAMP).source == "model"


# --- failover ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("failure", "reason", "status_class"),
    [
        (http_error(429), "rate_limited", "429"),
        (http_error(402), "payment_required", "402"),
        (http_error(503), "server_error", "5xx"),
        (AIProviderTimeout("timed out"), "timeout", None),
        (AIProviderUnavailable("not reachable"), "unavailable", None),
        (TimeoutError(), "timeout", None),
    ],
)
def test_an_availability_failure_moves_to_the_standby_and_is_logged(env, failure, reason, status_class) -> None:
    env.fake.script = {GEMMA: [failure]}
    result = route("word_translation", LAMP)
    assert env.fake.models() == [GEMMA, STANDBY]
    assert result.output == {"meaning": "cái đèn"} and result.provenance["model"] == STANDBY
    failed = [row for row in env.repo.operations if row["outcome"] == "failure"]
    assert len(failed) == 1
    assert (failed[0]["fallback_reason"], failed[0]["http_status_class"]) == (reason, status_class)
    assert (failed[0]["tier"], failed[0]["phase"], failed[0]["attempt"], failed[0]["router_version"]) == ("free", "pool", 1, "1")
    won = [row for row in env.repo.operations if row["outcome"] == "success"]
    assert (won[0]["model"], won[0]["attempt"], won[0]["tier"]) == (STANDBY, 2, "free")


def test_a_provider_that_keeps_failing_is_stood_down_and_not_hammered(env) -> None:
    env.fake.default = {GEMMA: {"meaning": "đèn"}, STANDBY: {"meaning": "đèn"}}
    env.fake.script = {GEMMA: [http_error(429)] * 10, STANDBY: [http_error(429)] * 10}
    for text in ("one", "two"):
        with pytest.raises(AIProviderError):
            route("word_translation", word(text))
    calls_before = len(env.fake.calls)
    with pytest.raises(AllProvidersUnavailable):
        route("word_translation", word("three"))
    assert len(env.fake.calls) == calls_before  # cooling down: not asked


@pytest.mark.parametrize("terminal", [AICapabilityDisabled("off"), AICapabilityConfigInvalid("bad"), ValueError("malformed")])
def test_a_terminal_error_is_raised_and_the_standby_is_not_asked(env, terminal) -> None:
    env.fake.script = {GEMMA: [terminal]}
    with pytest.raises(type(terminal)):
        route("word_translation", LAMP)
    assert env.fake.models() == [GEMMA]


# --- invalid output ---------------------------------------------------------------------------------------------


def test_invalid_output_retries_the_same_model_once_and_then_succeeds(env) -> None:
    env.fake.script = {GEMMA: [{"meaning": "lamp"}, {"meaning": "đèn"}]}
    result = route("word_translation", LAMP)
    assert env.fake.models() == [GEMMA, GEMMA] and result.provenance["model"] == GEMMA


def test_invalid_twice_fails_over_to_the_next_model(env) -> None:
    env.fake.script = {GEMMA: [{"meaning": "灯"}, {"meaning": "two\nlines"}]}
    result = route("word_translation", LAMP)
    assert env.fake.models() == [GEMMA, GEMMA, STANDBY]
    assert result.output == {"meaning": "cái đèn"}
    reasons = [row.get("fallback_reason") for row in env.repo.operations if row["outcome"] == "failure"]
    assert "invalid_output" in reasons


def test_invalid_everywhere_is_unavailable_and_nothing_invalid_is_cached(env) -> None:
    env.fake.script = {GEMMA: [{"meaning": "x\ny"}] * 2, STANDBY: [{"meaning": "x\ny"}] * 2}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert env.fake.models() == [GEMMA, GEMMA, STANDBY, STANDBY]
    env.clock.now += 61
    assert route("word_translation", LAMP).output == {"meaning": "đèn"}


# --- deadline ---------------------------------------------------------------------------------------------------


def test_each_attempt_is_bounded_by_what_remains_of_the_total_deadline(env) -> None:
    def slow(kwargs):
        env.clock.now += 3.0  # the primary eats three of the four seconds

    env.fake.on_call = slow
    env.fake.script = {GEMMA: [AIProviderTimeout("slow")]}
    route("word_translation", LAMP)
    assert env.fake.calls[0]["timeout"] <= 2.5
    assert 0 < env.fake.calls[1]["timeout"] <= 1.0 + 1e-9


def test_a_primary_with_a_long_configured_timeout_still_leaves_the_backup_its_time(env) -> None:
    """P0 QA: Groq (primary) timing out took the whole deadline, so the configured backup was never asked."""
    env.repo.config = config(timeout_seconds=30.0)

    def slow(kwargs):
        if kwargs["model"] == GEMMA:
            env.clock.now += kwargs["timeout"]  # the primary times out after exactly what it was given

    env.fake.on_call = slow
    env.fake.script = {GEMMA: [AIProviderTimeout("slow")]}
    result = route("word_translation", LAMP)
    assert env.fake.models() == [GEMMA, STANDBY], "the backup is asked after the primary's timeout"
    assert env.fake.calls[0]["timeout"] <= 4.0 - platform.BACKUP_RESERVE_SECONDS + 1e-9
    assert env.fake.calls[1]["timeout"] >= platform.BACKUP_RESERVE_SECONDS - 1e-9
    assert result.provenance["model"] == STANDBY
    failed = [row for row in env.repo.operations if row["outcome"] == "failure"]
    assert (failed[0]["fallback_reason"], failed[0]["failure_class"]) == ("timeout", "timeout"), "the breaker class"
    assert routing.provider_health.snapshot() == {} or all(
        state.get("reason") in (None, "timeout") for state in routing.provider_health.snapshot().values())


def test_a_deadline_that_is_already_gone_asks_nobody(env) -> None:
    with pytest.raises(AllProvidersUnavailable):
        route("word_translation", LAMP, deadline=env.clock.now - 1)
    assert env.fake.calls == []


def test_the_chain_stops_when_too_little_time_is_left_for_another_attempt(env) -> None:
    def slow(kwargs):
        env.clock.now += 3.95

    env.fake.on_call = slow
    env.fake.script = {GEMMA: [AIProviderTimeout("slow")]}
    with pytest.raises(AIProviderError):
        route("word_translation", LAMP)
    assert env.fake.models() == [GEMMA]  # 0.05 s left: the standby is not started


# --- disabled / not configured / bad input ----------------------------------------------------------------------


def test_a_disabled_capability_answers_nothing_and_asks_nobody(env) -> None:
    env.repo.config = config(enabled=False)
    with pytest.raises(AICapabilityDisabled):
        route("word_translation", LAMP)
    assert env.fake.calls == []


def test_a_disabled_capability_does_not_serve_old_cache_entries(env) -> None:
    route("word_translation", LAMP)
    env.repo.config = config(enabled=False)
    with pytest.raises(AICapabilityDisabled):
        route("word_translation", LAMP)


def test_without_a_configuration_the_capability_is_not_configured(env) -> None:
    env.repo.config = None
    with pytest.raises(AICapabilityNotConfigured):
        route("word_translation", LAMP)
    assert env.fake.calls == []


@pytest.mark.parametrize("raw", [word("the quick brown fox"), word("x" * 41), word("lamp", source="ja"), {"text": "lamp"},
                                 {**LAMP, "context": "A whole sentence."}])
def test_bad_input_is_refused_before_any_call(env, raw) -> None:
    with pytest.raises(RouterInputInvalid):
        route("word_translation", raw)
    assert env.fake.calls == []


def test_an_unrouted_capability_is_unsupported(env) -> None:
    from writing_coach.ai.base import AICapabilityUnsupported

    with pytest.raises(AICapabilityUnsupported):
        route("writing_evaluator", LAMP)


# --- languages --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "source", "target", "answer"),
    [("lamp", "en", "vi", "đèn"), ("图书馆", "zh", "vi", "thư viện"), ("图书馆", "zh", "en", "library")],
)
def test_english_and_chinese_sources_both_route(env, text, source, target, answer) -> None:
    env.fake.script = {GEMMA: [{"meaning": answer}]}
    assert route("word_translation", word(text, source, target)).output == {"meaning": answer}
    sent = json.loads(env.fake.calls[0]["messages"][-1]["content"])
    assert (sent["source_language"], sent["target_language"]) == (source, target)


# --- telemetry --------------------------------------------------------------------------------------------------


def test_no_word_prompt_or_meaning_reaches_telemetry_or_the_rollup(env) -> None:
    env.fake.script = {GEMMA: [http_error(429)]}
    route("word_translation", word("lamp"))
    route("word_translation", word("lamp"))  # a hit
    router_module.flush_rollup(force=True)
    blob = json.dumps(env.repo.operations + env.repo.events, ensure_ascii=False)
    for forbidden in ("lamp", "đèn", "cái đèn", "bilingual", "messages"):
        assert forbidden not in blob, forbidden
    assert env.repo.operations  # and it was recorded at all


def test_the_rollup_counts_requests_hits_and_the_model_used(env) -> None:
    env.fake.script = {GEMMA: [http_error(503)]}
    route("word_translation", word("lamp"))
    route("word_translation", word("lamp"))
    route("word_translation", word("book"))
    router_module.flush_rollup(force=True)
    (event,) = [e for e in env.repo.events if e["action"] == "ai.router.rollup"]
    assert event["entity_id"] == "word_translation"
    counters = event["payload"]["counters"]
    assert counters["requests"] == 3 and counters["cache_hits"] == 1 and counters["model_calls"] == 3
    assert counters["fallbacks"] == 1 and counters.get("failures", 0) == 0
    assert event["payload"]["models"][f"openrouter/{STANDBY}"] == 1
    assert event["payload"]["models"][f"openrouter/{GEMMA}"] == 1
    router_module.flush_rollup(force=True)
    assert len([e for e in env.repo.events if e["action"] == "ai.router.rollup"]) == 1  # nothing new: no empty row


def test_the_rollup_is_written_at_most_once_a_minute_by_ordinary_traffic(env) -> None:
    route("word_translation", word("lamp"))
    route("word_translation", word("lamp"))
    assert env.repo.events == []
    env.clock.now += 61
    route("word_translation", word("lamp"))
    assert len([e for e in env.repo.events if e["action"] == "ai.router.rollup"]) == 1


def test_free_calls_are_priced_at_zero_in_the_ledger_rows(env) -> None:
    route("word_translation", LAMP)
    row = env.repo.operations[-1]
    assert row["cost"]["state"] == "estimated" and row["cost"]["amount"] == 0


def test_validator_rejections_do_not_stand_the_provider_down(env) -> None:
    """P2-4: cooldown is for availability failures; three bad words in a row must not stop OpenRouter for everyone."""

    bad = {"meaning": "x" + chr(10) + "y"}
    for text in ("one", "two", "three"):
        env.fake.script = {GEMMA: [bad, bad], STANDBY: [bad, bad]}
        with pytest.raises(AIProviderError):
            route("word_translation", word(text))
    env.fake.calls.clear()
    env.fake.script = {}
    assert route("word_translation", word("four")).source == "model"  # still asked
    assert routing.provider_health.snapshot().get("openrouter", {}).get("cooling_down") is not True
