"""D-247: Orena chat falls back to a second provider when the first cannot answer - never silently, never after the
first token, never to a provider that may not receive learner text (D-104), never below the conversation's data class
(G8). The :8000 incident (2026-10-20): Gemini's project spending cap answered 429 to every call and chat said "busy"."""

from __future__ import annotations

import pytest

from tests.test_agent_turn import hermetic  # noqa: F401 - fixture
from tests.test_ai_agent_stream import Selected, StreamResponse, delta, finish, post_returning, provider
from writing_coach.ai import platform
from writing_coach.ai import routing
from writing_coach.ai.base import AIProviderError, AIProviderUnavailable, ChatFinished, ChatTextDelta

FIRST = ("gemini", "gemini-3.5-flash-lite")
SECOND = ("deepseek", "deepseek-flash")
ANSWER = [ChatTextDelta("Chào bạn"), ChatFinished("stop", prompt_tokens=40, completion_tokens=3)]


def spend_cap():
    error = AIProviderError("Gemini API returned HTTP 429. Your project has exceeded its monthly spending cap.")
    error.status_code = 429
    return error


@pytest.fixture()
def rig(monkeypatch):
    telemetry: list[dict] = []
    monkeypatch.setattr(platform, "_persist_operation_telemetry", telemetry.append)
    monkeypatch.setattr(platform, "_require_paid_funding", lambda *a, **k: None)
    monkeypatch.setattr(routing, "provider_health", routing.ProviderHealth())
    items: dict[str, Selected] = {}
    monkeypatch.setattr(platform, "providers", lambda: items)
    return telemetry, items


def turn(route=FIRST, fallback=SECOND):
    return platform.stream_agent_turn(messages=[{"role": "user", "content": "hi"}], tools=[], max_output_tokens=100,
                                      route=route, fallback=fallback)  # fmt: skip


def test_a_spend_capped_first_rung_falls_back_and_the_switch_is_recorded(rig):
    telemetry, items = rig
    items["gemini"] = Selected(fail=spend_cap(), provider_id="gemini")
    items["deepseek"] = Selected(events=ANSWER, provider_id="deepseek")
    assert list(turn()) == ANSWER  # the learner gets an answer, not "busy"
    first, second = telemetry
    assert first["provider"] == "gemini" and first["outcome"] == "failure"
    assert second["provider"] == "deepseek" and second["outcome"] == "success"
    assert second["provider_switch"] == {"from": "gemini", "to": "deepseek", "reason": first["failure_class"],
                                         "trigger": "failed"}  # fmt: skip
    # The breaker now holds Gemini's model down: the next turn goes straight to DeepSeek, Gemini is not asked again.
    items["gemini"].calls.clear()
    assert list(turn()) == ANSWER
    assert items["gemini"].calls == []
    assert telemetry[-1]["provider_switch"]["trigger"] == "down"


def test_both_rungs_failing_fail_the_round_and_both_are_recorded(rig):
    telemetry, items = rig
    items["gemini"] = Selected(fail=spend_cap(), provider_id="gemini")
    second = AIProviderError("DeepSeek API returned HTTP 503.")
    second.status_code = 503
    items["deepseek"] = Selected(fail=second, provider_id="deepseek")
    with pytest.raises(AIProviderError):
        list(turn())
    assert [(r["provider"], r["outcome"]) for r in telemetry] == [("gemini", "failure"), ("deepseek", "failure")]


def test_our_own_daily_ceiling_is_no_provider_failure_and_no_fallback(rig, monkeypatch):
    from writing_coach.ai import spend_gate

    _telemetry, items = rig

    def ceiling(*args, **kwargs):
        raise spend_gate.SpendCeilingReached()

    monkeypatch.setattr(platform, "_require_paid_funding", ceiling)
    items["gemini"] = Selected(events=ANSWER, provider_id="gemini")
    items["deepseek"] = Selected(events=ANSWER, provider_id="deepseek")
    with pytest.raises(spend_gate.SpendCeilingReached):
        list(turn())
    assert items["deepseek"].calls == []  # not tried: the ceiling refuses every paid rung alike
    assert routing.provider_health.is_available("gemini", FIRST[1])  # and Gemini is not blamed


def test_a_free_model_is_never_the_agents_fallback(rig, monkeypatch):
    """D-104 in `agent_fallback_route` itself: a provider that takes agent turns, but a zero-rated (free-tier) model."""
    _telemetry, items = rig
    monkeypatch.setattr(platform, "_platform_repository", None)
    items["groq"] = Selected(provider_id="groq")
    monkeypatch.setattr(platform, "check_model_allowed", lambda *a: None)
    monkeypatch.setenv(platform.AGENT_FALLBACK_ENV, "groq:llama-3.1-8b-instant")
    assert platform.agent_fallback_route() is None


def test_no_fallback_once_the_first_rung_has_answered_anything(rig):
    telemetry, items = rig

    def broken():
        yield ChatTextDelta("Chào")
        raise AIProviderUnavailable("dropped mid-answer")

    gemini = Selected(provider_id="gemini")
    gemini.stream_chat = lambda **kwargs: broken()
    items["gemini"] = gemini
    items["deepseek"] = Selected(events=ANSWER, provider_id="deepseek")
    with pytest.raises(AIProviderUnavailable):
        list(turn())
    assert items["deepseek"].calls == []  # never half an answer from one model and the rest from another


def test_without_a_fallback_a_failing_first_rung_fails_as_before(rig):
    _telemetry, items = rig
    items["gemini"] = Selected(fail=spend_cap(), provider_id="gemini")
    with pytest.raises(AIProviderError):
        list(turn(fallback=None))


def test_a_first_rung_that_answers_never_touches_the_fallback(rig):
    telemetry, items = rig
    items["gemini"] = Selected(events=ANSWER, provider_id="gemini")
    items["deepseek"] = Selected(events=ANSWER, provider_id="deepseek")
    assert list(turn()) == ANSWER
    assert items["deepseek"].calls == [] and "provider_switch" not in telemetry[0]


def test_the_fallback_route_must_take_agent_turns_and_may_receive_learner_text(rig, monkeypatch):
    _telemetry, items = rig
    monkeypatch.setattr(platform, "_platform_repository", None)
    items["deepseek"] = Selected(provider_id="deepseek")
    items["deepseek"].timeout = 30
    monkeypatch.setattr(platform, "check_model_allowed", lambda *a: None)
    monkeypatch.setenv(platform.AGENT_FALLBACK_ENV, "deepseek:deepseek-flash")
    assert platform.agent_fallback_route() == SECOND
    # OpenRouter may log prompts (D-104) and does not take agent turns: never the agent's fallback
    items["openrouter"] = Selected(provider_id="openrouter")
    monkeypatch.setenv(platform.AGENT_FALLBACK_ENV, "openrouter:meta-llama/llama-3.3-70b-instruct:free")
    assert platform.agent_fallback_route() is None
    monkeypatch.setenv(platform.AGENT_FALLBACK_ENV, "")
    assert platform.agent_fallback_route() is None


def test_the_agent_stream_sends_groq_its_reasoning_options(monkeypatch):
    """The "busy" trace found the stream path skipped GROQ_REQUEST_OPTIONS (only `_post_chat` sent them)."""
    seen = []
    post_returning(monkeypatch, StreamResponse([delta(content="ok"), finish("stop")]), seen)
    groq = provider(monkeypatch, provider_id="groq")
    list(groq.stream_chat(messages=[{"role": "user", "content": "hi"}], tools=[], model="qwen/qwen3.8-27b",
                          max_output_tokens=50))  # fmt: skip
    body = seen[0][1]["json"]
    assert body["reasoning_effort"] == "none" and body["reasoning_format"] == "hidden"


# --- the agent offers the fallback per turn, after G8 --------------------------------------------------------------


class FallbackRouter:
    def __init__(self, current, fallback):
        self.selection, self.second = current, fallback

    def current(self):
        return self.selection

    def usable(self, route):
        return True

    def fallback(self):
        return self.second


class PackOn:
    enabled = True

    def build(self, **kwargs):
        return None


def _turn_with(fallback, classes=None):
    from tests.test_agent_turn import run, runtime, turn_request
    from writing_coach.agent.fake_provider import reply
    from writing_coach.agent.provider import ModelRoute

    rt, fake = runtime([reply("a1")])
    rt.router = FallbackRouter(ModelRoute(*FIRST), ModelRoute(*fallback) if fallback else None)
    if classes is not None:
        rt.pack, rt.data_classes = PackOn(), classes
    run(rt, turn_request("q1"))
    return fake.requests[0]


def test_the_turn_offers_its_fallback_to_the_provider(hermetic):  # noqa: F811
    from writing_coach.agent.provider import ModelRoute

    assert _turn_with(SECOND).fallback == ModelRoute(*SECOND)
    assert _turn_with(None).fallback is None
    assert _turn_with(FIRST).fallback is None  # the same model is no second rung


def test_a_fallback_cleared_for_less_than_the_first_rung_is_withheld(hermetic):  # noqa: F811
    from writing_coach.agent.data_class import ProviderDataClasses

    lower = ProviderDataClasses.parse("gemini=learning_profile")  # deepseek unlisted: none
    assert _turn_with(SECOND, lower).fallback is None  # it would receive the same pack (G8)
    equal = ProviderDataClasses.parse("gemini=learning_profile,deepseek=learning_profile")
    assert _turn_with(SECOND, equal).fallback is not None


# --- the learner's own daily AI cost cap on an agent round (D-251) ---------------------------------------------


def _learner(monkeypatch, state, economy=SECOND):
    from writing_coach.ai import learner_cost
    from writing_coach.ai.routing import ProviderTarget

    target = ProviderTarget(*economy) if economy else None
    monkeypatch.setattr(learner_cost, "learner_cost_state", lambda user_key=None: learner_cost.LearnerCostState(
        state, account="u1", plan="plus", economy=target, resets_at="2026-10-22T00:00:00Z"))
    monkeypatch.setattr(platform, "agent_route_usable", lambda route: True)
    monkeypatch.setattr(platform, "_legacy_privacy_guard", lambda capability, item, model: None)


def test_over_the_plans_cap_a_paid_round_uses_the_economy_model(rig, monkeypatch):
    from writing_coach.ai import learner_cost

    telemetry, items = rig
    _learner(monkeypatch, learner_cost.DEGRADE)
    items["gemini"] = Selected(events=ANSWER, provider_id="gemini")
    items["deepseek"] = Selected(events=ANSWER, provider_id="deepseek")
    assert list(turn(fallback=None)) == ANSWER
    assert items["gemini"].calls == []  # the selected paid model is not asked
    assert telemetry[-1]["provider"] == "deepseek" and telemetry[-1]["learner_cost"] == "degraded"


def test_at_the_hard_ceiling_a_paid_round_is_refused_and_nothing_is_asked(rig, monkeypatch):
    from writing_coach.ai import learner_cost

    _telemetry, items = rig
    _learner(monkeypatch, learner_cost.REFUSE)
    items["gemini"] = Selected(events=ANSWER, provider_id="gemini")
    items["deepseek"] = Selected(events=ANSWER, provider_id="deepseek")
    with pytest.raises(learner_cost.LearnerCostCapReached):
        list(turn())
    assert items["gemini"].calls == [] and items["deepseek"].calls == []


def test_over_the_cap_with_no_economy_model_the_selected_one_answers_and_no_paid_fallback(rig, monkeypatch):
    from writing_coach.ai import learner_cost

    telemetry, items = rig
    _learner(monkeypatch, learner_cost.DEGRADE, economy=None)
    items["gemini"] = Selected(fail=spend_cap(), provider_id="gemini")
    items["deepseek"] = Selected(events=ANSWER, provider_id="deepseek")
    with pytest.raises(AIProviderError):
        list(turn())  # the paid fallback is withheld from a degraded learner
    assert items["deepseek"].calls == []
    assert telemetry[0]["learner_cost"] == "degraded_no_economy"


def test_under_the_cap_nothing_changes(rig, monkeypatch):
    from writing_coach.ai import learner_cost

    telemetry, items = rig
    _learner(monkeypatch, learner_cost.OK)
    items["gemini"] = Selected(events=ANSWER, provider_id="gemini")
    assert list(turn()) == ANSWER and "learner_cost" not in telemetry[0]
