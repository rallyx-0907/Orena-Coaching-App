"""Managed LLM API wrapper with a cache keyed by input hash (SPEC §2, §5.1).

Five provider families are wired in, because SPEC §5.3/§9 requires the model
that *verifies* a check item (blind solve) to differ from the model that
*generated* it — otherwise the same blind spot could pass its own work:

- ``anthropic``: Claude Messages API, structured output forced through a
  single tool call (SPEC needs one JSON object per block; tool-use is
  Anthropic's supported way to get that reliably).
- ``openai``: Chat Completions with ``response_format: json_schema`` (strict
  mode), OpenAI's equivalent.
- ``gemini``: ``generateContent`` with ``generationConfig.responseMimeType
  = application/json`` + ``responseSchema``, rewritten through
  ``to_gemini_schema`` for Gemini's narrower dialect (see that function).
  Uses the ``x-goog-api-key`` header, never the ``?key=`` query parameter --
  a secret does not belong in a URL. **Exercised live** 2026-09-28 (real
  generate calls; see grammar_lab/sandbox/).
- ``groq``: an OpenAI-compatible ``chat/completions`` endpoint
  (api.groq.com/openai/v1), ``response_format: json_schema`` with
  ``strict: false`` (Groq's own docs list only best-effort mode as broadly
  supported; strict mode is model-limited). A genuinely different model
  family from Gemini even though the request shape mirrors OpenAI's.
  **Exercised live** 2026-09-28 (blind-solve calls).
- ``deepseek``: an OpenAI-compatible endpoint (api.deepseek.com), but
  **only** ``response_format: {"type": "json_object"}`` (no schema
  enforcement at all -- DeepSeek's own docs list no ``json_schema`` mode).
  The schema is instead spelled out in the prompt text, and the system
  message must contain the word "json" per DeepSeek's own requirement for
  this mode to activate. Weaker structural guarantee than the other four
  providers. **Exercised live** 2026-09-28: the first real run came back
  with empty ``content`` for every call. Cause: DeepSeek's thinking mode is
  **on by default at "high" effort** (its own docs), and for a schema this
  size it reliably spent the entire ``max_tokens`` budget on
  ``reasoning_content`` before ever writing to ``content``.

  ``deepseek_thinking`` (``"off" | "low" | "high"``, default ``"off"``)
  controls this rather than hard-coding it off: "off" sends
  ``{"type": "disabled"}``; "low"/"high" send ``{"type": "enabled"}`` with
  that ``reasoning_effort`` and, since reasoning shares the one
  ``max_tokens`` budget with the final answer, automatically add headroom
  (+4096 for low, +8192 for high) on top of the caller's ``max_tokens`` so
  there is still room left for ``content`` after the reasoning. The CLI
  records which level a run used in ``reports/<run_id>/generate.json``, and
  exposes it as ``--deepseek-thinking`` for the phase-1 gold-set comparison
  of off vs. low (SPEC §5.4's calibration idea, applied to provider choice).

  A 3-attempt retry remains as a safety net for the separate "occasionally
  empty" case DeepSeek's own json-mode docs warn about even outside
  thinking mode.

Every key is read from its own environment variable
(``ANTHROPIC_API_KEY``/``OPENAI_API_KEY``/``GEMINI_API_KEY``/``GROQ_API_KEY``/
``DEEPSEEK_API_KEY``), never a literal in code or in a compose file, and is
never logged: an error message built from a provider's raw response text is
passed through ``secrets_redact.redact`` before it becomes an exception
message, in case a provider ever echoes a credential back.

A failed call can still have been billed (DeepSeek bills reasoning tokens
even when ``content`` ends up empty): every attempt's usage is accumulated
and attached to the ``LLMError`` as ``.usage``, so a caller that catches the
error can still account for the real cost rather than silently losing it.

Gemini calls go through ``rate_limit.limiter_for("gemini", ...)`` and retry
on HTTP 429 with backoff: this project's Gemini key is shared with other
live traffic and has a measured ceiling of roughly 25-30 requests/minute
(see ``pipeline/rate_limit.py``). DeepSeek gets its own named bucket
(``"deepseek"``) if a caller ever rate-limits it -- never ``"gemini"`` -- but
no interval is forced by default: DeepSeek publishes a 500-2500 concurrent
request limit, nothing like Gemini's measured ceiling, so there is nothing
to protect it against here yet.

Every call is cached on disk keyed by a hash of everything that determines
the output (provider, model, system+user prompt, schema, temperature, seed),
so a run repeated with the same input costs nothing the second time and the
pipeline stays idempotent (SPEC §5, "chạy lại được độc lập và idempotent").
The cache is content-addressed and never expires; delete
``grammar_lab/.cache/llm/`` to force regeneration.

Pricing in ``PRICING`` is a list-price snapshot, not a live lookup: check the
provider's current pricing page before trusting a cost estimate for a real
budget decision (SPEC §9, "Managed API nào dùng... ngân sách mỗi lần chạy").
Groq pricing for the model this project uses could not be confirmed live and
is deliberately left out of the table; its cost reports as ``None`` (never a
guessed number) until a checked price is added. DeepSeek's peak, cache-miss
rate is used (the conservative case -- off-peak/cached traffic is billed
less); checked live 2026-09-28.
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
from grammar_lab.pipeline.rate_limit import GEMINI_MIN_INTERVAL_SECONDS, backoff_delay, limiter_for
from grammar_lab.pipeline.secrets_redact import redact

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = LAB_ROOT / ".cache" / "llm"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

GEMINI_MAX_RETRIES = 5

PROVIDERS = {"anthropic", "openai", "gemini", "groq", "deepseek"}
_ENV_VAR_BY_PROVIDER = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
}

DEEPSEEK_THINKING_LEVELS = {"off", "low", "high"}
# Reasoning shares one max_tokens budget with the final answer (see module
# docstring): headroom added on top of the caller's max_tokens so content
# still has room to be written after the reasoning phase.
DEEPSEEK_THINKING_HEADROOM = {"off": 0, "low": 4096, "high": 8192}

# USD per 1,000,000 tokens (input, output). Checked live against
# platform.claude.com/docs/en/about-claude/pricing, platform.openai.com/docs/pricing
# and ai.google.dev/gemini-api/docs/pricing on 2026-09-27 -- still only a
# snapshot, re-check before trusting a cost estimate (see module docstring).
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
    "gpt-6-luna": (0.10, 0.50),
    "gpt-6-sol": (2.0, 10.0),
    "gpt-6-astra": (10.0, 50.0),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    # "openai/gpt-oss-120b" (Groq) deliberately omitted -- see module docstring.
    # DeepSeek: peak, cache-miss rate (api-docs.deepseek.com/quick_start/pricing, checked 2026-09-28).
    "deepseek-flash": (0.30, 1.20),
    "deepseek-v4-pro": (1.32, 3.96),
}


class LLMError(RuntimeError):
    """A provider call failed, or its response did not match the requested schema."""

    def __init__(self, message: str, *, status_code: int | None = None, usage: LLMUsage | None = None) -> None:
        super().__init__(redact(message))
        self.status_code = status_code
        # Set when a provider can bill a failed call (e.g. DeepSeek's reasoning
        # tokens on an empty-content response) -- see module docstring.
        self.usage = usage


def to_gemini_schema(schema: Any) -> Any:
    """Rewrite a draft-2020-12 JSON Schema into Gemini's narrower ``Schema``
    proto dialect (confirmed live 2026-09-28: a full JSON Schema payload is
    rejected outright, not merely ignored in the unsupported parts):

    - ``additionalProperties`` is not a recognised field at all -- dropped.
    - ``type`` must be one string, never an array; a ``["X", "null"]`` union
      becomes ``type: "X", nullable: true``.
    - ``prefixItems`` (tuple validation) is not supported; an array using it
      collapses to plain ``items`` with the common type of its prefix
      schemas (this codebase's only use, ``example.seg``, is a homogeneous
      string tuple, so this loses no information here; a genuinely
      mixed-type tuple would fall back to ``{"type": "string"}``, best-effort
      rather than a schema Gemini would reject).

    Only degrades what does not fit through this specific parser; a plain
    Anthropic/OpenAI/Groq schema (draft-2020-12, checked against the real
    APIs) does not go through this function at all.
    """
    if isinstance(schema, list):
        return [to_gemini_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    result = {key: value for key, value in schema.items() if key != "additionalProperties"}

    type_value = result.get("type")
    if isinstance(type_value, list):
        non_null = [t for t in type_value if t != "null"]
        if "null" in type_value:
            result["nullable"] = True
        result["type"] = non_null[0] if non_null else "null"

    if "prefixItems" in result:
        prefix_items = result.pop("prefixItems")
        types = {item.get("type") for item in prefix_items if isinstance(item, dict)}
        result["items"] = {"type": types.pop()} if len(types) == 1 else {"type": "string"}
    elif "items" in result:
        result["items"] = to_gemini_schema(result["items"])

    if "properties" in result:
        result["properties"] = {key: to_gemini_schema(value) for key, value in result["properties"].items()}

    for key in ("allOf", "anyOf", "oneOf"):
        if key in result:
            result[key] = [to_gemini_schema(item) for item in result[key]]

    return result


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
        deepseek_thinking: str = "off",
    ) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}; expected one of {sorted(PROVIDERS)}")
        if deepseek_thinking not in DEEPSEEK_THINKING_LEVELS:
            raise ValueError(f"unknown deepseek_thinking {deepseek_thinking!r}; expected one of {sorted(DEEPSEEK_THINKING_LEVELS)}")
        self.provider = provider
        self.model = model
        self.cache_dir = cache_dir
        self.deepseek_thinking = deepseek_thinking
        self.api_key = api_key if api_key is not None else os.environ.get(_ENV_VAR_BY_PROVIDER[provider], "")
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
            raise LLMError(f"no API key for provider {self.provider!r}; set {_ENV_VAR_BY_PROVIDER[self.provider]}")
        if self.provider == "anthropic":
            data, usage = self._call_anthropic(system, user, json_schema, schema_name, temperature, max_tokens)
        elif self.provider == "openai":
            data, usage = self._call_openai_compatible(
                OPENAI_API_URL, system, user, json_schema, schema_name, temperature, seed, max_tokens, strict=True,
            )
        elif self.provider == "groq":
            data, usage = self._call_openai_compatible(
                GROQ_API_URL, system, user, json_schema, schema_name, temperature, seed, max_tokens, strict=False,
            )
        elif self.provider == "deepseek":
            data, usage = self._call_deepseek(system, user, json_schema, temperature, max_tokens)
        else:
            data, usage = self._call_gemini_with_retry(system, user, json_schema, temperature, max_tokens)

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

    def _call_openai_compatible(
        self, url: str, system: str, user: str, json_schema: dict[str, Any], schema_name: str,
        temperature: float, seed: int | None, max_tokens: int, *, strict: bool,
    ) -> tuple[dict[str, Any], LLMUsage]:
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": json_schema, "strict": strict},
            },
        }
        if seed is not None:
            body["seed"] = seed
        response = self._post(url, body, headers={
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        })
        choices = response.get("choices") or []
        if not choices:
            raise LLMError(f"response had no choices: {response!r}")
        content = choices[0]["message"]["content"]
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"response content was not JSON: {content!r}") from exc
        usage_raw = response.get("usage", {})
        usage = LLMUsage(int(usage_raw.get("prompt_tokens", 0)), int(usage_raw.get("completion_tokens", 0)))
        return data, usage

    def _call_deepseek(
        self, system: str, user: str, json_schema: dict[str, Any], temperature: float, max_tokens: int,
    ) -> tuple[dict[str, Any], LLMUsage]:
        """DeepSeek's json_object mode has no schema parameter at all (see module
        docstring): the schema is spelled out in the prompt instead, and the
        word "json" must appear for the mode to activate at all.

        ``self.deepseek_thinking`` controls thinking mode (off by default --
        see module docstring for why, and for the +4096/+8192 max_tokens
        headroom added for low/high so reasoning does not crowd out the
        final answer). A short retry remains as a safety net for the
        "occasionally empty" case DeepSeek's own json-mode docs separately
        warn about, independent of thinking mode.
        """
        schema_instruction = (
            "\n\nRespond with a single JSON object and nothing else (no markdown fences, no commentary), "
            f"matching this JSON Schema exactly:\n{json.dumps(json_schema, ensure_ascii=False)}"
        )
        if self.deepseek_thinking == "off":
            thinking: dict[str, Any] = {"type": "disabled"}
        else:
            thinking = {"type": "enabled"}
            max_tokens += DEEPSEEK_THINKING_HEADROOM[self.deepseek_thinking]
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "thinking": thinking,
            "messages": [
                {"role": "system", "content": system + schema_instruction},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        if self.deepseek_thinking != "off":
            body["reasoning_effort"] = self.deepseek_thinking
        spent_input = 0
        spent_output = 0
        last_message = "DeepSeek returned empty content 3 times (a known json_object-mode issue per its own docs)"
        for attempt in range(3):
            response = self._post(DEEPSEEK_API_URL, body, headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            })
            usage_raw = response.get("usage", {})
            spent_input += int(usage_raw.get("prompt_tokens", 0))
            spent_output += int(usage_raw.get("completion_tokens", 0))
            choices = response.get("choices") or []
            if not choices:
                raise LLMError(f"response had no choices: {response!r}", usage=LLMUsage(spent_input, spent_output))
            content = choices[0]["message"]["content"]
            if not content:
                last_message = f"DeepSeek returned empty content on attempt {attempt + 1}/3"
                continue
            try:
                data = json.loads(content)
            except json.JSONDecodeError as exc:
                raise LLMError(f"response content was not JSON: {content!r}",
                                usage=LLMUsage(spent_input, spent_output)) from exc
            return data, LLMUsage(spent_input, spent_output)
        raise LLMError(last_message, usage=LLMUsage(spent_input, spent_output))

    def _call_gemini_with_retry(
        self, system: str, user: str, json_schema: dict[str, Any], temperature: float, max_tokens: int,
    ) -> tuple[dict[str, Any], LLMUsage]:
        limiter = limiter_for("gemini", GEMINI_MIN_INTERVAL_SECONDS)
        for attempt in range(GEMINI_MAX_RETRIES):
            limiter.wait()
            try:
                return self._call_gemini(system, user, json_schema, temperature, max_tokens)
            except LLMError as exc:
                if exc.status_code != 429 or attempt == GEMINI_MAX_RETRIES - 1:
                    raise
                time.sleep(backoff_delay(attempt))
        raise AssertionError("unreachable")  # loop always returns or raises

    def _call_gemini(
        self, system: str, user: str, json_schema: dict[str, Any], temperature: float, max_tokens: int,
    ) -> tuple[dict[str, Any], LLMUsage]:
        url = GEMINI_API_URL_TEMPLATE.format(model=self.model)
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": to_gemini_schema(json_schema),
            },
        }
        # x-goog-api-key, not ?key=<api_key> in the URL: a secret does not belong in a URL/query string.
        response = self._post(url, body, headers={"x-goog-api-key": self.api_key, "content-type": "application/json"})
        candidates = response.get("candidates") or []
        if not candidates:
            raise LLMError(f"Gemini response had no candidates: {response!r}")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = next((part["text"] for part in parts if "text" in part), None)
        if text is None:
            raise LLMError(f"Gemini response had no text part: {response!r}")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"Gemini response text was not JSON: {text!r}") from exc
        usage_raw = response.get("usageMetadata", {})
        usage = LLMUsage(int(usage_raw.get("promptTokenCount", 0)), int(usage_raw.get("candidatesTokenCount", 0)))
        return data, usage

    def _post(self, url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        try:
            response = self._client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"request to {url} failed: {exc}") from exc
        if response.status_code >= 400:
            raise LLMError(f"{url} returned {response.status_code}: {response.text[:2000]}", status_code=response.status_code)
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
