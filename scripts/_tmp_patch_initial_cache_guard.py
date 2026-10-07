from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# llm_client.py: one-call fail-closed cache requirement.
path = Path("grammar_lab/pipeline/llm_client.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '        max_tokens: int = 4096,\n        check_schema: bool = True,\n    ) -> LLMResult:\n',
    '        max_tokens: int = 4096,\n        check_schema: bool = True,\n        require_cache: bool = False,\n    ) -> LLMResult:\n',
    "LLMClient.complete signature",
)
text = replace_once(
    text,
    '        if self.cache_only:\n            raise LLMError(\n                f"cache-only mode: no cached completion for {self.provider}:{self.model}; provider call blocked"\n            )\n',
    '        if require_cache:\n            raise LLMError(\n                f"initial-cache-required mode: no cached completion for {self.provider}:{self.model}; "\n                "full provider call blocked"\n            )\n\n        if self.cache_only:\n            raise LLMError(\n                f"cache-only mode: no cached completion for {self.provider}:{self.model}; provider call blocked"\n            )\n',
    "LLMClient require-cache gate",
)
path.write_text(text, encoding="utf-8")


# generate.py: require only the initial full candidate; repair calls remain provider-capable.
path = Path("grammar_lab/pipeline/generate.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '    max_full_attempts: int = V04_SEMANTIC_ATTEMPTS\n    paid_repairs: bool = True\n',
    '    max_full_attempts: int = V04_SEMANTIC_ATTEMPTS\n    paid_repairs: bool = True\n    require_initial_cache: bool = False\n',
    "Generator dataclass field",
)
text = replace_once(
    text,
    '            check_schema=False,  # legacy v0.2/0.3 path\n        )\n',
    '            check_schema=False,  # legacy v0.2/0.3 path\n            require_cache=self.require_initial_cache,\n        )\n',
    "legacy initial completion",
)
text = replace_once(
    text,
    '                    schema_name="grammar_point_v04", max_tokens=V04_MAX_TOKENS,\n                )\n',
    '                    schema_name="grammar_point_v04", max_tokens=V04_MAX_TOKENS,\n                    require_cache=self.require_initial_cache,\n                )\n',
    "v04 initial completion",
)
path.write_text(text, encoding="utf-8")


# cli.py: surface the guard and propagate/record it.
path = Path("grammar_lab/pipeline/cli.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '    cache_only: bool = typer.Option(\n        False, "--cache-only",\n        help="Never call the provider. Re-evaluate only completions already present in the local LLM cache.",\n    ),\n',
    '    cache_only: bool = typer.Option(\n        False, "--cache-only",\n        help="Never call the provider. Re-evaluate only completions already present in the local LLM cache.",\n    ),\n    require_initial_cache: bool = typer.Option(\n        False, "--require-initial-cache",\n        help=(\n            "Require the full lesson candidate to come from local cache, while still allowing "\n            "provider-backed structure/semantic repair calls. Prevents accidental full regeneration."\n        ),\n    ),\n',
    "CLI option",
)
text = replace_once(
    text,
    '        + (", cache-only" if cache_only else "")\n    )\n',
    '        + (", cache-only" if cache_only else "")\n        + (", require-initial-cache" if require_initial_cache else "")\n    )\n',
    "CLI mode output",
)
text = replace_once(
    text,
    '                    max_full_attempts=effective_max_full_attempts,\n                    paid_repairs=effective_paid_repairs,\n                )\n',
    '                    max_full_attempts=effective_max_full_attempts,\n                    paid_repairs=effective_paid_repairs,\n                    require_initial_cache=require_initial_cache,\n                )\n',
    "Generator propagation",
)
text = replace_once(
    text,
    '        "cache_only": cache_only,\n        "replay_cache_file": str(replay_cache_file) if replay_cache_file is not None else None,\n',
    '        "cache_only": cache_only,\n        "require_initial_cache": require_initial_cache,\n        "replay_cache_file": str(replay_cache_file) if replay_cache_file is not None else None,\n',
    "run metadata",
)
path.write_text(text, encoding="utf-8")


# Permanent regression tests.
Path("grammar_lab/tests/test_initial_cache_guard.py").write_text(r'''import inspect
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
''', encoding="utf-8")
