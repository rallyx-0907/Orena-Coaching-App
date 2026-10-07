import inspect
import tempfile
from pathlib import Path

import httpx

from grammar_lab.pipeline.llm_client import LLMClient, LLMError


def main() -> None:
    assert "require_cache" in inspect.signature(LLMClient.complete).parameters

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": "network must not be called"})

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"type": "boolean"}},
    }
    with tempfile.TemporaryDirectory() as temp:
        client = LLMClient(
            "deepseek",
            "deepseek-flash",
            api_key="dummy",
            cache_dir=Path(temp),
            transport=httpx.MockTransport(handler),
        )
        try:
            try:
                client.complete(
                    system="json test",
                    user="test",
                    json_schema=schema,
                    require_cache=True,
                )
            except LLMError as exc:
                assert "cache" in str(exc).lower()
            else:
                raise AssertionError("require_cache=True must fail closed on cache miss")
        finally:
            client.close()
    assert calls == 0, f"provider was called {calls} time(s)"


if __name__ == "__main__":
    main()
