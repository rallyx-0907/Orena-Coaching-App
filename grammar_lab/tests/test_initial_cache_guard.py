import inspect
from dataclasses import fields
from pathlib import Path

import httpx
import pytest

from grammar_lab.pipeline.cli import generate_corpus_command
from grammar_lab.pipeline.generate import Generator
from grammar_lab.pipeline.llm_client import LLMClient, LLMError


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["ok"],
    "properties": {"ok": {"type": "boolean"}},
}


def test_require_cache_blocks_provider_on_miss(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": "must not be called"})

    with LLMClient(
        "deepseek", "deepseek-flash", api_key="dummy", cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(LLMError, match="initial-cache-required"):
            client.complete(
                system="json test", user="miss", json_schema=SCHEMA,
                require_cache=True,
            )
    assert calls == 0


def test_require_cache_accepts_existing_cache_without_provider(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        })

    kwargs = dict(system="json test", user="hit", json_schema=SCHEMA)
    transport = httpx.MockTransport(handler)
    with LLMClient(
        "deepseek", "deepseek-flash", api_key="dummy", cache_dir=tmp_path,
        transport=transport,
    ) as client:
        first = client.complete(**kwargs)
        second = client.complete(**kwargs, require_cache=True)
    assert first.cached is False
    assert second.cached is True
    assert second.data == {"ok": True}
    assert calls == 1


def test_initial_cache_guard_is_exposed_through_generator_and_corpus_cli() -> None:
    assert "require_cache" in inspect.signature(LLMClient.complete).parameters
    assert "require_initial_cache" in {field.name for field in fields(Generator)}
    assert "require_initial_cache" in inspect.signature(generate_corpus_command).parameters
