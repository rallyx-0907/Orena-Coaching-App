from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any


_SUSPICIOUS_TELEMETRY_VALUE = re.compile(
    r"(?:^[a-z][a-z0-9+.-]*://|[?#]|(?:api[_-]?key|token|secret|password|authorization)\s*=)",
    re.IGNORECASE,
)


class AIProviderError(RuntimeError):
    """Provider failure carrying optional normalized operation telemetry."""

    telemetry: dict[str, Any] | None = None
    rate_limit: dict[str, int | None] | None = None


class AIProviderUnavailable(AIProviderError):
    pass


class AIProviderNotConfigured(AIProviderUnavailable):
    """The server lacks the credentials or endpoint configuration for a provider."""


class AIModelCatalogEmpty(AIProviderUnavailable):
    """Live discovery succeeded but returned no usable models."""


class AIModelUnavailable(AIProviderUnavailable):
    """The selected model cannot currently satisfy a provider request."""


class AIProviderResponseInvalid(AIProviderError):
    """A provider response did not satisfy the requested capability schema."""


class AICapabilityError(RuntimeError):
    """Base error for capability configuration and routing contracts."""

    telemetry: dict[str, Any] | None = None


class AICapabilityDisabled(AICapabilityError):
    pass


class AICapabilityNotConfigured(AICapabilityError):
    pass


class AICapabilityConfigInvalid(AICapabilityError):
    """Persisted or proposed capability configuration is malformed."""


class AICapabilityUnsupported(AICapabilityError):
    pass


class AIProviderUnsupportedOperation(AICapabilityUnsupported):
    """A known provider cannot perform a capability's declared operation."""


@dataclass(frozen=True)
class ChatTextDelta:
    """A piece of streamed assistant text."""

    text: str


@dataclass(frozen=True)
class ChatToolCall:
    """A complete native tool call; `arguments` is the provider's JSON text."""

    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ChatFinished:
    """The end of one streamed round, with whatever usage the provider reported."""

    finish_reason: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    rate_limit: dict[str, int | None] | None = None


ChatStreamEvent = ChatTextDelta | ChatToolCall | ChatFinished


@dataclass
class AIResult:
    data: dict[str, Any]
    provider: str
    model: str
    runtime: dict[str, Any]

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


def normalized_usage(runtime: object) -> dict[str, int | None]:
    """Keep provider usage honest: malformed or absent counts remain unknown."""

    source = runtime if isinstance(runtime, dict) else {}
    result: dict[str, int | None] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = source.get(key)
        if type(value) is int and value >= 0:
            result[key] = value
        else:
            result[key] = None
    return result


_RATE_LIMIT_KEYS = (
    "requests_limit",
    "requests_remaining",
    "tokens_limit",
    "tokens_remaining",
)

_COST_STATES = frozenset({"estimated", "unpriced", "partial", "unknown"})


def normalized_rate_limit(value: object) -> dict[str, int | None]:
    """Keep only provider-reported non-negative integer rate-limit evidence."""

    source = value if isinstance(value, dict) else {}
    result: dict[str, int | None] = {}
    for key in _RATE_LIMIT_KEYS:
        item = source.get(key)
        result[key] = item if type(item) is int and item >= 0 else None
    return result


def normalized_cost(value: object) -> dict[str, Any] | None:
    """Keep only the versioned, prompt-free cost evidence contract."""

    if not isinstance(value, dict) or value.get("state") not in _COST_STATES:
        return None
    currency = value.get("currency")
    if currency is not None and (not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency)):
        currency = None
    amount = value.get("amount")
    if type(amount) not in {int, float} or not math.isfinite(float(amount)) or amount < 0:
        amount = None
    provenance = value.get("provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    version = provenance.get("catalog_version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\.v[0-9]+", version):
        version = None
    provider = provenance.get("provider")
    provider = str(provider or "")[:40] or None
    if provider and not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", provider):
        provider = None
    model = provenance.get("model")
    model = str(model or "")[:160] or None
    if model and _SUSPICIOUS_TELEMETRY_VALUE.search(model):
        model = "[redacted]"
    reason = provenance.get("reason")
    if not isinstance(reason, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,39}", reason):
        reason = None
    rates = {}
    for key in ("input_per_million", "output_per_million"):
        rate = provenance.get(key)
        rates[key] = round(float(rate), 8) if type(rate) in {int, float} and math.isfinite(float(rate)) and rate >= 0 else None
    return {
        "state": value["state"],
        "currency": currency,
        "amount": round(float(amount), 8) if amount is not None else None,
        "provenance": {
            "catalog_version": version,
            "provider": provider,
            "model": model,
            **rates,
            "reason": reason,
        },
    }


def normalized_latency(value: object) -> int | None:
    """Return a non-negative elapsed duration or unknown."""

    if type(value) not in {int, float} or not math.isfinite(float(value)):
        return None
    return max(0, round(float(value)))


def telemetry_error_class(error: BaseException) -> str:
    """Map typed provider/capability failures to a stable, non-secret label."""

    names = {
        AICapabilityDisabled: "capability_disabled",
        AICapabilityNotConfigured: "capability_not_configured",
        AICapabilityConfigInvalid: "capability_invalid",
        AICapabilityUnsupported: "capability_unsupported",
        AIProviderNotConfigured: "provider_not_configured",
        AIModelCatalogEmpty: "model_catalog_empty",
        AIModelUnavailable: "model_unavailable",
        AIProviderResponseInvalid: "provider_response_invalid",
        AIProviderUnavailable: "provider_unavailable",
        AIProviderError: "provider_error",
    }
    for error_type, label in names.items():
        if isinstance(error, error_type):
            return label
    return "operation_failed"


def sanitize_telemetry(value: object) -> dict[str, Any] | None:
    """Return the allowlisted, prompt-free event shape safe for persistence."""

    if not isinstance(value, dict):
        return None
    origin = value.get("origin")
    if not isinstance(origin, str) or origin not in {"learner", "operator_test", "configuration"}:
        origin = None
    capability = str(value.get("capability") or "")
    if capability != "legacy" and capability != "[invalid]" and not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", capability):
        capability = "[invalid]"
    provider = str(value.get("provider") or "")[:40] or None
    if provider and not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", provider):
        provider = "[redacted]"
    model = str(value.get("model") or "")[:160] or None
    model_redacted = bool(value.get("model_redacted"))
    if model and _SUSPICIOUS_TELEMETRY_VALUE.search(model):
        model, model_redacted = "[redacted]", True
    usage = normalized_usage(value.get("usage"))
    outcome = value.get("outcome")
    if outcome not in {"success", "failure"}:
        return None
    error_class = value.get("error_class")
    if not isinstance(error_class, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", error_class):
        error_class = None
    result = {
        "capability": capability,
        "origin": origin,
        "provider": provider,
        "model": model,
        "model_redacted": model_redacted,
        "outcome": outcome,
        "error_class": error_class,
        "latency_ms": normalized_latency(value.get("latency_ms")),
        "usage": usage,
        "rate_limit": normalized_rate_limit(value.get("rate_limit")),
        "quota_available": "unknown",
    }
    cost = normalized_cost(value.get("cost"))
    if cost is not None:
        result["cost"] = cost
    return result


def extract_json_object(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for pos, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[pos:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value

    raise AIProviderResponseInvalid("AI provider did not return a complete JSON object.")
