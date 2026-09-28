from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from grammar_lab.pipeline.llm_client import LLMClient, LLMError

SCHEMA = {"type": "object", "properties": {"greeting": {"type": "string"}}, "required": ["greeting"]}


def _anthropic_transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": "emit_output", "input": {"greeting": "hi"}}],
            "usage": {"input_tokens": 10, "output_tokens": 4},
        })
    return httpx.MockTransport(handler)


def _openai_transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"greeting": "hi"})}}],
            "usage": {"prompt_tokens": 8, "completion_tokens": 3},
        })
    return httpx.MockTransport(handler)


def _gemini_transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": json.dumps({"greeting": "hi"})}]}}],
            "usageMetadata": {"promptTokenCount": 6, "candidatesTokenCount": 2},
        })
    return httpx.MockTransport(handler)


def _groq_transport(calls: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({"greeting": "hi"})}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        })
    return httpx.MockTransport(handler)


_MODEL_BY_PROVIDER = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-6-luna",
    "gemini": "gemini-3.5-flash-lite",
    "groq": "openai/gpt-oss-120b",
}


def client(tmp_path: Path, provider: str, transport: httpx.MockTransport) -> LLMClient:
    return LLMClient(provider, _MODEL_BY_PROVIDER[provider], api_key="test-key", cache_dir=tmp_path, transport=transport)


def test_anthropic_returns_tool_use_input(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = client(tmp_path, "anthropic", _anthropic_transport(calls))
    result = c.complete(system="s", user="u", json_schema=SCHEMA)
    assert result.data == {"greeting": "hi"}
    assert result.usage.input_tokens == 10 and result.usage.output_tokens == 4
    assert result.cached is False
    assert len(calls) == 1


def test_openai_returns_parsed_json_content(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = client(tmp_path, "openai", _openai_transport(calls))
    result = c.complete(system="s", user="u", json_schema=SCHEMA)
    assert result.data == {"greeting": "hi"}
    assert result.usage.input_tokens == 8 and result.usage.output_tokens == 3
    assert len(calls) == 1


def test_gemini_returns_parsed_json_from_the_text_part(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = client(tmp_path, "gemini", _gemini_transport(calls))
    result = c.complete(system="s", user="u", json_schema=SCHEMA)
    assert result.data == {"greeting": "hi"}
    assert result.usage.input_tokens == 6 and result.usage.output_tokens == 2
    assert len(calls) == 1


def test_gemini_sends_api_key_as_header_never_in_the_url(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    client(tmp_path, "gemini", _gemini_transport(calls)).complete(system="s", user="u", json_schema=SCHEMA)
    request = calls[0]
    assert "key=" not in str(request.url)
    assert request.headers["x-goog-api-key"] == "test-key"


def test_gemini_response_without_candidates_raises(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})
    c = client(tmp_path, "gemini", httpx.MockTransport(handler))
    with pytest.raises(LLMError, match="candidates"):
        c.complete(system="s", user="u", json_schema=SCHEMA)


def test_gemini_retries_on_429_and_then_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("grammar_lab.pipeline.llm_client.time.sleep", lambda _seconds: None)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(429, text="quota exceeded")
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": json.dumps({"greeting": "hi"})}]}}],
            "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
        })

    c = client(tmp_path, "gemini", httpx.MockTransport(handler))
    result = c.complete(system="s", user="u", json_schema=SCHEMA)
    assert result.data == {"greeting": "hi"}
    assert len(calls) == 3  # two 429s, then success


def test_gemini_gives_up_after_max_retries_on_429(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("grammar_lab.pipeline.llm_client.time.sleep", lambda _seconds: None)
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(429, text="quota exceeded")

    c = client(tmp_path, "gemini", httpx.MockTransport(handler))
    with pytest.raises(LLMError, match="429"):
        c.complete(system="s", user="u", json_schema=SCHEMA)
    assert len(calls) == 5  # GEMINI_MAX_RETRIES, no more


def test_gemini_does_not_retry_on_a_non_429_error(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, text="bad request")

    c = client(tmp_path, "gemini", httpx.MockTransport(handler))
    with pytest.raises(LLMError, match="400"):
        c.complete(system="s", user="u", json_schema=SCHEMA)
    assert len(calls) == 1


def test_error_message_redacts_the_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "secret-value-should-not-leak")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="rejected key secret-value-should-not-leak")

    c = LLMClient("gemini", "gemini-3.5-flash-lite", api_key="secret-value-should-not-leak",
                  cache_dir=tmp_path, transport=httpx.MockTransport(handler))
    with pytest.raises(LLMError) as excinfo:
        c.complete(system="s", user="u", json_schema=SCHEMA)
    assert "secret-value-should-not-leak" not in str(excinfo.value)


def test_groq_returns_parsed_json_content(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = client(tmp_path, "groq", _groq_transport(calls))
    result = c.complete(system="s", user="u", json_schema=SCHEMA)
    assert result.data == {"greeting": "hi"}
    assert result.usage.input_tokens == 5 and result.usage.output_tokens == 2
    assert len(calls) == 1


def test_groq_uses_best_effort_not_strict_schema_mode(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    client(tmp_path, "groq", _groq_transport(calls)).complete(system="s", user="u", json_schema=SCHEMA)
    sent = json.loads(calls[0].content)
    assert sent["response_format"]["json_schema"]["strict"] is False


def test_groq_and_openai_hit_different_urls(tmp_path: Path) -> None:
    groq_calls: list[httpx.Request] = []
    openai_calls: list[httpx.Request] = []
    client(tmp_path, "groq", _groq_transport(groq_calls)).complete(system="s", user="u", json_schema=SCHEMA)
    client(tmp_path, "openai", _openai_transport(openai_calls)).complete(system="s", user="u", json_schema=SCHEMA)
    assert "groq.com" in str(groq_calls[0].url)
    assert "openai.com" in str(openai_calls[0].url)


def test_unknown_provider_still_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="groq"):
        LLMClient("cohere", "some-model", api_key="k", cache_dir=tmp_path)


def test_second_call_with_same_input_is_cached_and_makes_no_request(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = client(tmp_path, "anthropic", _anthropic_transport(calls))
    c.complete(system="s", user="u", json_schema=SCHEMA)
    second = c.complete(system="s", user="u", json_schema=SCHEMA)
    assert second.cached is True
    assert second.data == {"greeting": "hi"}
    assert len(calls) == 1  # no second request


def test_different_input_is_a_cache_miss(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = client(tmp_path, "anthropic", _anthropic_transport(calls))
    c.complete(system="s", user="u", json_schema=SCHEMA)
    c.complete(system="s", user="different", json_schema=SCHEMA)
    assert len(calls) == 2


def test_cache_is_shared_across_client_instances_with_the_same_cache_dir(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    transport = _anthropic_transport(calls)
    client(tmp_path, "anthropic", transport).complete(system="s", user="u", json_schema=SCHEMA)
    second = client(tmp_path, "anthropic", transport)
    result = second.complete(system="s", user="u", json_schema=SCHEMA)
    assert result.cached is True
    assert len(calls) == 1


def test_missing_api_key_raises_before_any_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    calls: list[httpx.Request] = []
    c = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="", cache_dir=tmp_path,
                  transport=_anthropic_transport(calls))
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        c.complete(system="s", user="u", json_schema=SCHEMA)
    assert len(calls) == 0


def test_http_error_status_raises_llm_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="rate limited")
    c = client(tmp_path, "anthropic", httpx.MockTransport(handler))
    with pytest.raises(LLMError, match="429"):
        c.complete(system="s", user="u", json_schema=SCHEMA)


def test_anthropic_response_without_tool_use_raises_llm_error(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"content": [{"type": "text", "text": "oops"}], "usage": {}})
    c = client(tmp_path, "anthropic", httpx.MockTransport(handler))
    with pytest.raises(LLMError, match="tool_use"):
        c.complete(system="s", user="u", json_schema=SCHEMA)


def test_usage_cost_uses_the_pricing_table(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = client(tmp_path, "anthropic", _anthropic_transport(calls))
    result = c.complete(system="s", user="u", json_schema=SCHEMA)
    cost = result.usage.cost_usd(result.model)
    assert cost is not None and cost > 0


def test_unknown_model_cost_is_none(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    c = LLMClient("anthropic", "claude-unknown-model", api_key="k", cache_dir=tmp_path,
                  transport=_anthropic_transport(calls))
    result = c.complete(system="s", user="u", json_schema=SCHEMA)
    assert result.usage.cost_usd(result.model) is None
