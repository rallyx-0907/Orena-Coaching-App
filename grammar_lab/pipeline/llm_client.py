"""Managed LLM API wrapper with a cache keyed by input hash (SPEC §2, §5.1).

Two provider families are wired in, because SPEC §5.3/§9 requires the model
that *verifies* a check item (blind solve) to differ from the model that
*generated* it — otherwise the same blind spot could pass its own work:

- ``anthropic``: Claude Messages API, structured output forced through a
  single tool call (SPEC needs one JSON object per block; tool-use is
  Anthropic's supported way to get that reliably).
- ``openai``: Chat Completions with ``response_format: json_schema`` (strict
  mode), OpenAI's equivalent.

Every call is cached on disk keyed by a hash of everything that determines
the output (provider, model, system+user prompt, schema, temperature, seed),
so a run repeated with the same input costs nothing the second time and the
pipeline stays idempotent (SPEC §5, "chạy lại được độc lập và idempotent").
The cache is content-addressed and never expires; delete
``grammar_lab/.cache/llm/`` to force regeneration.

Pricing in ``PRICING`` is a list-price snapshot, not a live lookup: check the
provider's current pricing page before trusting a cost estimate for a real
budget decision (SPEC §9, "Managed API nào dùng... ngân sách mỗi lần chạy").
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from grammar_lab.pipeline.jsonio import read_json, write_json

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = LAB_ROOT / ".cache" / "llm"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# USD per 1,000,000 tokens (input, output). Checked live against
# platform.claude.com/docs/en/about-claude/pricing and
# platform.openai.com/docs/pricing on 2026-09-27 -- still only a snapshot,
# re-check before trusting a cost estimate (see module docstring).
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6-sol": (2.0, 10.0),
    "gpt-6-astra": (10.0, 50.0),
}


class LLMError(RuntimeError):
    """A provider call failed, or its response did not match the requested schema."""


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int
    output_tokens: int

    def cost_usd(self, model: str) -> float | None:
        prices = PRICING.get(model)
        if prices is None:
            return None
        in_price, out_price = prices
        return self.input_tokens / 1_000_000 * in_price + self.output_tokens / 1_000_000 * out_price


@dataclass(frozen=True)
class LLMResult:
    data: dict[str, Any]
    usage: LLMUsage
    model: str
    provider: str
    cached: bool


def _cache_key(*, provider: str, model: str, system: str, user: str, schema: dict[str, Any],
                temperature: float, seed: int | None) -> str:
    payload = json.dumps(
        {"provider": provider, "model": model, "system": system, "user": user, "schema": schema,
         "temperature": temperature, "seed": seed},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LLMClient:
    """One provider, one model. Build a second instance for the second model family."""

    def __init__(
        self,
        provider: str,
        model: str,
        *,
        api_key: str | None = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 120.0,
    ) -> None:
        if provider not in {"anthropic", "openai"}:
            raise ValueError(f"unknown provider {provider!r}; expected 'anthropic' or 'openai'")
        self.provider = provider
        self.model = model
        self.cache_dir = cache_dir
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        self.api_key = api_key if api_key is not None else os.environ.get(env_var, "")
        self._client = httpx.Client(transport=transport, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LLMClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- public API ------------------------------------------------------------------

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        schema_name: str = "output",
        temperature: float = 0.0,
        seed: int | None = None,
        max_tokens: int = 4096,
    ) -> LLMResult:
        """One JSON object matching ``json_schema``, cached by input hash."""
        key = _cache_key(
            provider=self.provider, model=self.model, system=system, user=user,
            schema=json_schema, temperature=temperature, seed=seed,
        )
        cached = self._read_cache(key)
        if cached is not None:
            usage = LLMUsage(cached["usage"]["input_tokens"], cached["usage"]["output_tokens"])
            return LLMResult(cached["data"], usage, self.model, self.provider, cached=True)

        if not self.api_key:
            raise LLMError(
                f"no API key for provider {self.provider!r}; set "
                f"{'ANTHROPIC_API_KEY' if self.provider == 'anthropic' else 'OPENAI_API_KEY'}"
            )
        if self.provider == "anthropic":
            data, usage = self._call_anthropic(system, user, json_schema, schema_name, temperature, max_tokens)
        else:
            data, usage = self._call_openai(system, user, json_schema, schema_name, temperature, seed, max_tokens)

        self._write_cache(key, data, usage)
        return LLMResult(data, usage, self.model, self.provider, cached=False)

    # -- providers ---------------------------------------------------------------------

    def _call_anthropic(
        self, system: str, user: str, json_schema: dict[str, Any], schema_name: str,
        temperature: float, max_tokens: int,
    ) -> tuple[dict[str, Any], LLMUsage]:
        tool_name = f"emit_{schema_name}"
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "tools": [{"name": tool_name, "description": f"Emit the {schema_name} JSON object.", "input_schema": json_schema}],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        response = self._post(ANTHROPIC_API_URL, body, headers={
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        })
        tool_use = next((block for block in response.get("content", []) if block.get("type") == "tool_use"), None)
        if tool_use is None:
            raise LLMError(f"Anthropic response had no tool_use block: {response!r}")
        usage_raw = response.get("usage", {})
        usage = LLMUsage(int(usage_raw.get("input_tokens", 0)), int(usage_raw.get("output_tokens", 0)))
        return tool_use["input"], usage

    def _call_openai(
        self, system: str, user: str, json_schema: dict[str, Any], schema_name: str,
        temperature: float, seed: int | None, max_tokens: int,
    ) -> tuple[dict[str, Any], LLMUsage]:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": json_schema, "strict": True},
            },
        }
        if seed is not None:
            body["seed"] = seed
        response = self._post(OPENAI_API_URL, body, headers={
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        })
        choices = response.get("choices") or []
        if not choices:
            raise LLMError(f"OpenAI response had no choices: {response!r}")
        content = choices[0]["message"]["content"]
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"OpenAI response content was not JSON: {content!r}") from exc
        usage_raw = response.get("usage", {})
        usage = LLMUsage(int(usage_raw.get("prompt_tokens", 0)), int(usage_raw.get("completion_tokens", 0)))
        return data, usage

    def _post(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        try:
            response = self._client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"request to {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise LLMError(f"{url} returned {response.status_code}: {response.text[:2000]}")
        return response.json()

    # -- cache ---------------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / self.provider / f"{key}.json"

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            return read_json(path)
        except ValueError:
            return None

    def _write_cache(self, key: str, data: dict[str, Any], usage: LLMUsage) -> None:
        write_json(self._cache_path(key), {
            "provider": self.provider,
            "model": self.model,
            "cached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens},
            "data": data,
        })
