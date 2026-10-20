"""#438: a provider that is out of service is not told to the learner as "Orena is busy, try again".

On :8000 every agent round failed before it started with `Gemini API returned HTTP 429. Your project has exceeded
its monthly spending cap.` The 200 stream ended with `error{provider_unavailable, retry}` and the copy "Orena đang
bận, thử lại sau nhé" - a wait that cannot cure a spent cap. The class and the fallback stay the contract's (§4.1);
only the sentence tells the truth.
"""

from __future__ import annotations

import pytest

from writing_coach.agent.capability_registry import load_capability_registry
from writing_coach.agent.errors import ProviderOutOfService, ProviderUnavailable
from writing_coach.agent.platform_provider import PlatformAgentTurnProvider
from writing_coach.agent.provider import ProviderMessage, ProviderTurnRequest
from writing_coach.agent.runtime import build_tool_registry
from writing_coach.agent.schemas import TurnRequest
from writing_coach.agent.session import SessionCache
from writing_coach.agent.tools import LearnerScope
from writing_coach.agent.turn import AgentRuntime
from writing_coach.ai.base import AIProviderError, AIProviderNotConfigured, AIProviderTimeout

SPEND_CAP = ("Gemini API returned HTTP 429. Your project has exceeded its monthly spending cap. Please go to AI Studio "
             "at https://ai.studio/spend to manage your project spend cap.")
LEARNER = LearnerScope(user_key="learner-1", language="en")


def provider_error(text: str, status: int | None) -> AIProviderError:
    error = AIProviderError(text)
    error.status_code = status
    return error


def refusing(exc: Exception) -> PlatformAgentTurnProvider:
    def stream_turn(**kwargs):
        raise exc

    return PlatformAgentTurnProvider(stream_turn)


def failing_mid_stream(exc: Exception) -> PlatformAgentTurnProvider:
    def stream_turn(**kwargs):
        def events():
            raise exc
            yield  # pragma: no cover

        return events()

    return PlatformAgentTurnProvider(stream_turn)


ROUND = ProviderTurnRequest(messages=(ProviderMessage(role="user", content="hi"),), tools=())


@pytest.mark.parametrize(
    "exc",
    [
        provider_error(SPEND_CAP, 429),
        provider_error("OpenRouter returned HTTP 402. Insufficient credits.", 402),
        provider_error("Groq returned HTTP 401. Invalid API Key", 401),
        provider_error("OpenAI returned HTTP 429. insufficient_quota", 429),
        AIProviderNotConfigured("no key"),
    ],
)
def test_a_provider_a_wait_cannot_cure_is_out_of_service(exc):
    with pytest.raises(ProviderOutOfService):
        list(refusing(exc).stream(ROUND))
    with pytest.raises(ProviderOutOfService):
        list(failing_mid_stream(exc).stream(ROUND))


@pytest.mark.parametrize(
    "exc",
    [
        provider_error("Groq returned HTTP 429. Rate limit reached for model qwen in tokens per minute", 429),
        # Gemini's ordinary per-minute 429 names billing too; it is still a short wait (review P2 of #448).
        provider_error("Gemini API returned HTTP 429. You exceeded your current quota, please check your plan and "
                       "billing details. Quota exceeded for metric: generate_content_free_tier_requests, limit: 15, "
                       "model: gemini-flash. Please retry in 21s.", 429),
        provider_error("Gemini API returned HTTP 503. The model is overloaded.", 503),
        AIProviderTimeout("timed out"),
    ],
)
def test_a_passing_failure_is_still_only_unavailable(exc):
    with pytest.raises(ProviderUnavailable) as caught:
        list(refusing(exc).stream(ROUND))
    assert not isinstance(caught.value, ProviderOutOfService)


def turn(support: str) -> TurnRequest:
    return TurnRequest.model_validate({
        "contract_version": 5,
        "trigger": "message",
        "message": "What should I study today?",
        "client": {"ui_version": "t", "supported_actions": ["navigate"], "supported_intents": ["vocabulary.review_due"]},
        "context": {"surface": "vocabulary.my_language",
                    "locale": {"interface": support, "support": support, "target": "en"}},
    })  # fmt: skip


def run(provider, support):
    tools = build_tool_registry(writing_review=lambda essay_id: None)
    rt = AgentRuntime(provider=provider, tools=tools, capabilities=load_capability_registry(registered_tools=tools.names()),
                      sessions=SessionCache())  # fmt: skip
    return list(rt.run(turn(support), LEARNER))


@pytest.mark.parametrize(
    ("support", "said"),
    [
        ("vi", "Orena tạm thời chưa trò chuyện được. Các bài học vẫn dùng bình thường."),
        ("en", "Orena can't chat right now. Your lessons still work."),
        ("zh-CN", "Orena 暂时无法聊天，课程仍可正常使用。"),
    ],
)
def test_the_spent_cap_ends_the_stream_with_the_true_sentence_in_the_contract_shape(support, said):
    last = run(refusing(provider_error(SPEND_CAP, 429)), support)[-1]
    assert last.name == "error"
    assert (last.error_class, last.fallback, last.message) == ("provider_unavailable", "retry", said)
    assert "bận" not in last.message and "busy" not in last.message and "Gemini" not in last.message


@pytest.mark.parametrize(
    "text",
    [
        "Groq returned HTTP 429. Rate limit reached",
        "Gemini API returned HTTP 429. You exceeded your current quota, please check your plan and billing details. "
        "Please retry in 21s.",
    ],
)
def test_a_passing_failure_still_says_busy(text):
    last = run(refusing(provider_error(text, 429)), "vi")[-1]
    assert (last.error_class, last.fallback, last.message) == ("provider_unavailable", "retry", "Orena đang bận, thử lại sau nhé.")
