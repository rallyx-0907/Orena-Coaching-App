"""Streaming chat with native tool calls, and the agent's legacy-routed round (Slice 1b)."""

from __future__ import annotations

import json

import pytest
import requests

from writing_coach.agent.errors import ProviderUnavailable
from writing_coach.agent.platform_provider import PlatformAgentTurnProvider, parse_arguments, wire_message, wire_tool
from writing_coach.agent.provider import (
    ProviderMessage,
    ProviderToolSpec,
    ProviderTurnRequest,
    TextDelta,
    ToolCallRequest,
    TurnFinished,
)
from writing_coach.ai import platform
from writing_coach.ai.base import (
    AIProviderError,
    AIProviderNotConfigured,
    AIProviderResponseInvalid,
    AIProviderUnavailable,
    ChatFinished,
    ChatTextDelta,
    ChatToolCall,
)
from writing_coach.ai.capabilities import AIOperation
from writing_coach.ai.providers import OpenAICompatibleProvider, get_provider_definition


class StreamResponse:
    def __init__(self, chunks, *, status_code=200, headers=None, error=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._lines = []
        for chunk in chunks:
            self._lines.append(chunk if isinstance(chunk, bytes) else f"data: {json.dumps(chunk)}".encode())
            self._lines.append(b"")
        self._error = error
        self._payload = payload
        self.closed = False
        self.read = 0

    def iter_lines(self):
        for line in self._lines:
            self.read += 1
            yield line
        if self._error:
            raise self._error

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def close(self):
        self.closed = True


def provider(monkeypatch, provider_id="gemini"):
    monkeypatch.setenv("TEST_AI_KEY", "test-key-value")
    return OpenAICompatibleProvider(
        provider_id=provider_id,
        name="Test Provider",
        api_key_env="TEST_AI_KEY",
        base_url_env="TEST_AI_URL",
        default_base_url="https://provider.invalid/v1",
        models_env="TEST_AI_MODELS",
    )


def post_returning(monkeypatch, response, seen=None):
    def post(url, **kwargs):
        if seen is not None:
            seen.append((url, kwargs))
        return response

    monkeypatch.setattr(requests, "post", post)


def delta(**content):
    return {"choices": [{"index": 0, "delta": content, "finish_reason": None}]}


def finish(reason, usage=None):
    chunk = {"choices": [{"index": 0, "delta": {}, "finish_reason": reason}]}
    if usage:
        chunk["usage"] = usage
    return chunk


def run(item, **kwargs):
    return list(
        item.stream_chat(
            messages=[{"role": "user", "content": "hi"}],
            tools=kwargs.pop("tools", []),
            model="m-1",
            max_output_tokens=300,
            **kwargs,
        )
    )


# --- OpenAICompatibleProvider.stream_chat ------------------------------------------------


def test_the_request_is_a_streaming_chat_with_tools(monkeypatch):
    seen = []
    post_returning(monkeypatch, StreamResponse([finish("stop"), b"data: [DONE]"]), seen)
    tools = [{"type": "function", "function": {"name": "get_x", "description": "x", "parameters": {"type": "object"}}}]
    item = provider(monkeypatch)
    run(item, tools=tools, temperature=0.2)
    url, kwargs = seen[0]
    assert url == "https://provider.invalid/v1/chat/completions"
    assert kwargs["stream"] is True and kwargs["timeout"] == (min(10.0, item.timeout), float(item.timeout))
    assert kwargs["headers"]["Authorization"] == "Bearer test-key-value"
    body = kwargs["json"]
    assert body["stream"] is True and body["tools"] == tools and body["max_tokens"] == 300
    assert body["temperature"] == 0.2 and "stream_options" not in body


def test_openai_is_asked_for_usage_on_the_stream(monkeypatch):
    seen = []
    post_returning(monkeypatch, StreamResponse([finish("stop")]), seen)
    run(provider(monkeypatch, "openai"))
    assert seen[0][1]["json"]["stream_options"] == {"include_usage": True}


def test_text_deltas_then_a_finish_with_usage(monkeypatch):
    usage = {"prompt_tokens": 120, "completion_tokens": 9, "prompt_tokens_details": {"cached_tokens": 100}}
    response = StreamResponse([b": keep-alive", delta(content="Xin "), delta(content="chào"), finish("stop", usage), b"data: [DONE]"])
    post_returning(monkeypatch, response)
    events = run(provider(monkeypatch))
    assert events[:2] == [ChatTextDelta("Xin "), ChatTextDelta("chào")]
    done = events[-1]
    assert isinstance(done, ChatFinished) and done.finish_reason == "stop"
    assert (done.prompt_tokens, done.completion_tokens, done.cached_tokens) == (120, 9, 100)
    assert response.closed


def test_tool_call_fragments_are_joined_by_index(monkeypatch):
    chunks = [
        delta(tool_calls=[{"index": 0, "id": "call_a", "type": "function", "function": {"name": "get_due_vocabulary", "arguments": ""}}]),
        delta(tool_calls=[{"index": 1, "id": "call_b", "function": {"name": "suggest_next", "arguments": '{"intent"'}}]),
        delta(tool_calls=[{"index": 0, "function": {"arguments": '{"limit"'}}]),
        delta(tool_calls=[{"index": 0, "function": {"arguments": ": 3}"}}]),
        delta(tool_calls=[{"index": 1, "function": {"arguments": ': "review_due"}'}}]),
        finish("tool_calls"),
    ]
    post_returning(monkeypatch, StreamResponse(chunks))
    events = run(provider(monkeypatch))
    assert events[:2] == [
        ChatToolCall(id="call_a", name="get_due_vocabulary", arguments='{"limit": 3}'),
        ChatToolCall(id="call_b", name="suggest_next", arguments='{"intent": "review_due"}'),
    ]
    assert events[-1].finish_reason == "tool_calls"


def test_whole_calls_without_an_index_stay_separate(monkeypatch):
    chunks = [
        delta(tool_calls=[
            {"id": "c1", "function": {"name": "cite_evidence", "arguments": '{"evidence_ids": ["e1"]}'}},
            {"id": "c2", "function": {"name": "set_voice_style", "arguments": '{"voice_style": "brief_ack"}'}},
        ]),
        finish("stop"),
    ]  # fmt: skip
    post_returning(monkeypatch, StreamResponse(chunks))
    events = run(provider(monkeypatch))
    calls = [e for e in events if isinstance(e, ChatToolCall)]
    assert [(c.id, c.name) for c in calls] == [("c1", "cite_evidence"), ("c2", "set_voice_style")]
    # a round that asked for tools ends as a tool round, whatever label the endpoint gave it
    assert events[-1].finish_reason == "tool_calls"


def test_http_failures_raise_before_streaming_and_carry_the_rate_limit(monkeypatch):
    response = StreamResponse(
        [], status_code=429, headers={"x-ratelimit-remaining-requests": "0"}, payload={"error": {"message": "slow down"}}
    )
    post_returning(monkeypatch, response)
    with pytest.raises(AIProviderError, match="HTTP 429") as caught:
        run(provider(monkeypatch))
    assert caught.value.rate_limit["requests_remaining"] == 0 and response.closed


@pytest.mark.parametrize("error, kind", [(requests.ConnectionError(), "not reachable"), (requests.Timeout(), "timed out")])
def test_transport_failures_are_typed(monkeypatch, error, kind):
    def post(*args, **kwargs):
        raise error

    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(AIProviderUnavailable, match=kind):
        run(provider(monkeypatch))


def test_a_stream_that_breaks_or_lies_is_typed(monkeypatch):
    post_returning(monkeypatch, StreamResponse([delta(content="a")], error=requests.ConnectionError()))
    with pytest.raises(AIProviderUnavailable):
        run(provider(monkeypatch))
    post_returning(monkeypatch, StreamResponse([b"data: {not json"]))
    with pytest.raises(AIProviderResponseInvalid):
        run(provider(monkeypatch))
    post_returning(monkeypatch, StreamResponse([{"error": {"message": "boom"}}]))
    with pytest.raises(AIProviderError):
        run(provider(monkeypatch))
    post_returning(monkeypatch, StreamResponse([delta(tool_calls=[{"index": 0, "function": {"arguments": "{}"}}]), finish("tool_calls")]))
    with pytest.raises(AIProviderResponseInvalid, match="without a name"):
        run(provider(monkeypatch))


def test_an_unconfigured_provider_never_calls_out(monkeypatch):
    monkeypatch.delenv("TEST_AI_KEY", raising=False)
    item = OpenAICompatibleProvider(
        provider_id="gemini", name="Test Provider", api_key_env="TEST_AI_KEY_UNSET", base_url_env="TEST_AI_URL",
        default_base_url="https://provider.invalid/v1", models_env="TEST_AI_MODELS",
    )  # fmt: skip
    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("called out"))
    with pytest.raises(AIProviderNotConfigured):
        run(item)


def test_the_client_can_stop_a_stream(monkeypatch):
    response = StreamResponse([delta(content=str(i)) for i in range(50)])
    post_returning(monkeypatch, response)
    seen = []
    for event in provider(monkeypatch).stream_chat(
        messages=[], tools=[], model="m-1", max_output_tokens=10, should_stop=lambda: len(seen) >= 2
    ):
        seen.append(event)
    assert len(seen) == 2 and response.closed and response.read < 10


def test_only_the_managed_chat_providers_stream_agent_turns():
    for provider_id in ("openai", "deepseek", "groq", "gemini"):
        assert get_provider_definition(provider_id).supports(AIOperation.AGENT_TURN)
    assert not get_provider_definition("ollama").supports(AIOperation.AGENT_TURN)


# --- platform.stream_agent_turn: the legacy selection, never local -----------------------


class Selected:
    def __init__(self, kind="cloud", configured=True, events=(), fail=None, provider_id="gemini"):
        self.id = provider_id
        self.name = "Selected"
        self.kind = kind
        self.configured = configured
        self._events = list(events)
        self._fail = fail
        self.calls = []

    def stream_chat(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail:
            raise self._fail
        return iter(self._events)


@pytest.fixture()
def telemetry(monkeypatch):
    records = []
    monkeypatch.setattr(platform, "_persist_operation_telemetry", records.append)
    return records


def stream(monkeypatch, item, model="gemini-3.5-flash-lite"):
    monkeypatch.setattr(platform, "active_selection", lambda: (item, model))
    return platform.stream_agent_turn(messages=[{"role": "user", "content": "hi"}], tools=[], max_output_tokens=100)


def test_a_local_model_is_refused_not_used(monkeypatch, telemetry):
    item = Selected(kind="local", provider_id="ollama")
    with pytest.raises(AIProviderUnavailable, match="managed provider"):
        stream(monkeypatch, item, model="qwen3:8b")
    assert item.calls == []
    assert telemetry[0]["outcome"] == "failure" and telemetry[0]["capability"] == "agent_turn_fast"


def test_an_unconfigured_selection_is_refused(monkeypatch, telemetry):
    with pytest.raises(AIProviderUnavailable):
        stream(monkeypatch, Selected(configured=False))


def test_a_round_streams_and_is_recorded_once(monkeypatch, telemetry):
    events = [ChatTextDelta("Chào"), ChatFinished("stop", prompt_tokens=50, completion_tokens=4)]
    item = Selected(events=events)
    assert list(stream(monkeypatch, item)) == events
    assert item.calls[0]["model"] == "gemini-3.5-flash-lite"
    (record,) = telemetry
    assert record["outcome"] == "success" and record["provider"] == "gemini" and record["origin"] == "learner"
    assert record["usage"]["prompt_tokens"] == 50 and record["usage"]["completion_tokens"] == 4


def test_a_failure_mid_stream_is_recorded_and_raised(monkeypatch, telemetry):
    def broken():
        yield ChatTextDelta("a")
        raise AIProviderUnavailable("dropped")

    item = Selected()
    item.stream_chat = lambda **kwargs: broken()
    with pytest.raises(AIProviderUnavailable):
        list(stream(monkeypatch, item))
    assert [r["outcome"] for r in telemetry] == ["failure"]


# --- the agent's adapter -----------------------------------------------------------------


def test_messages_and_tools_take_the_openai_wire_shape():
    call = ToolCallRequest("c1", "get_due_vocabulary", {"limit": 3})
    assert wire_message(ProviderMessage(role="assistant", content="", tool_calls=(call,))) == {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "get_due_vocabulary", "arguments": '{"limit": 3}'}}],
    }
    assert wire_message(ProviderMessage(role="tool", content="{}", tool_call_id="c1")) == {
        "role": "tool", "tool_call_id": "c1", "content": "{}",
    }  # fmt: skip
    assert wire_tool(ProviderToolSpec("get_x", "x", {"type": "object"})) == {
        "type": "function", "function": {"name": "get_x", "description": "x", "parameters": {"type": "object"}},
    }  # fmt: skip


def test_the_adapter_converts_events_and_hides_provider_failures():
    def stream_turn(**kwargs):
        assert kwargs["tools"][0]["type"] == "function"
        return iter(
            [
                ChatTextDelta("Chào"),
                ChatToolCall("c1", "get_due_vocabulary", '{"limit": 2}'),
                ChatToolCall("c2", "suggest_next", "not json"),
                ChatFinished("tool_calls", prompt_tokens=None, completion_tokens=7),
            ]
        )

    adapter = PlatformAgentTurnProvider(stream_turn)
    request = ProviderTurnRequest(
        messages=(ProviderMessage(role="user", content="hi"),), tools=(ProviderToolSpec("get_due_vocabulary", "d", {}),)
    )
    assert list(adapter.stream(request)) == [
        TextDelta("Chào"),
        ToolCallRequest("c1", "get_due_vocabulary", {"limit": 2}),
        ToolCallRequest("c2", "suggest_next", {}),
        TurnFinished(input_tokens=None, output_tokens=7, finish_reason="tool_calls"),
    ]

    def refuses(**kwargs):
        raise AIProviderUnavailable("Gemini key rejected: region blocked")

    with pytest.raises(ProviderUnavailable) as caught:
        list(PlatformAgentTurnProvider(refuses).stream(request))
    assert "Gemini" not in str(caught.value)


def test_arguments_that_are_not_an_object_read_as_none():
    assert parse_arguments('{"a": 1}') == {"a": 1}
    assert parse_arguments("") == {} and parse_arguments("[1]") == {} and parse_arguments("{oops") == {}


def test_each_read_waits_no_longer_than_the_turn_has_left(monkeypatch):
    seen = []
    post_returning(monkeypatch, StreamResponse([finish("stop")]), seen)
    run(provider(monkeypatch), read_timeout=7.5)
    assert seen[0][1]["timeout"] == (7.5, 7.5)
    run(provider(monkeypatch), read_timeout=45)
    assert seen[1][1]["timeout"] == (10.0, 45)


def test_usage_is_asked_for_only_where_the_endpoint_documents_it(monkeypatch):
    for provider_id, asked in (("openai", True), ("deepseek", True), ("gemini", False), ("groq", False)):
        seen = []
        post_returning(monkeypatch, StreamResponse([finish("stop")]), seen)
        run(provider(monkeypatch, provider_id))
        assert ("stream_options" in seen[0][1]["json"]) is asked, provider_id


def test_unreported_usage_is_unknown_not_zero(monkeypatch):
    post_returning(monkeypatch, StreamResponse([delta(content="a"), finish("stop")]))
    done = run(provider(monkeypatch))[-1]
    assert done.prompt_tokens is None and done.completion_tokens is None


def test_a_round_the_learner_leaves_is_still_recorded(monkeypatch, telemetry):
    def endless():
        yield ChatTextDelta("a")
        yield ChatTextDelta("b")

    item = Selected()
    item.stream_chat = lambda **kwargs: endless()
    events = stream(monkeypatch, item)
    next(events)
    events.close()
    (record,) = telemetry
    assert record["outcome"] == "failure" and record["error_class"] == "client_abandoned"


def test_the_turn_budget_reaches_the_provider(monkeypatch, telemetry):
    item = Selected(events=[ChatFinished("stop", prompt_tokens=1, completion_tokens=1)])
    monkeypatch.setattr(platform, "active_selection", lambda: (item, "m"))
    list(platform.stream_agent_turn(messages=[], tools=[], max_output_tokens=10, timeout_seconds=12.0))
    assert item.calls[0]["read_timeout"] == 12.0
