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
    # The HTTP status the provider answered with, set by the provider adapter; None when there was no response.
    status_code: int | None = None


class AIProviderUnavailable(AIProviderError):
    pass


class AIProviderTimeout(AIProviderUnavailable):
    """The provider did not answer within the time this attempt was given."""


class AIProviderNotConfigured(AIProviderUnavailable):
    """The server lacks the credentials or endpoint configuration for a provider."""


class AIModelCatalogEmpty(AIProviderUnavailable):
    """Live discovery succeeded but returned no usable models."""


class AIModelUnavailable(AIProviderUnavailable):
    """The selected model cannot currently satisfy a provider request."""


class AIProviderResponseInvalid(AIProviderError):
    """A provider response did not satisfy the requested capability schema."""


class AIOutputInvalid(AIProviderResponseInvalid):
    """The answer parsed but failed the capability contract's own semantic validation (router, G2)."""


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
    """A complete native tool call; `arguments` is the provider's JSON text.

    `extra` is what the provider attached to the call for itself (Gemini's
    `extra_content` holds a thought signature) and requires back, verbatim, when
    the call is sent in the next round. It is opaque: never parsed, never shown.
    """

    id: str
    name: str
    arguments: str
    extra: dict[str, Any] | None = None


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

def reported_completion_tokens(usage: object) -> int | None:
    """The completion tokens a provider billed, thinking included (D-221).

    An OpenAI-compatible endpoint reports `completion_tokens` and `total_tokens`. Some (Gemini's) leave the model's
    thinking tokens out of the first and keep them in the second, and every vendor bills them at the output rate. When
    the total exceeds prompt plus completion the difference is thinking, and is counted with the completion; when the
    completion already holds it (total equals the sum) nothing is added. An absent completion stays unknown."""

    source = usage if isinstance(usage, dict) else {}
    prompt, completion, total = (source.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
    if type(completion) is not int or completion < 0:
        return None
    if type(prompt) is int and prompt >= 0 and type(total) is int and total > prompt + completion:
        return total - prompt
    return completion


def normalized_usage(runtime: object) -> dict[str, int | float | None]:
    """Keep provider usage honest: malformed or absent counts remain unknown."""

    source = runtime if isinstance(runtime, dict) else {}
    result: dict[str, int | float | None] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = source.get(key)
        if type(value) is int and value >= 0:
            result[key] = value
        else:
            result[key] = None
    # An audio request's length (speech recognition, pronunciation scoring): kept only when reported.
    seconds = source.get("audio_seconds")
    if type(seconds) in {int, float} and math.isfinite(float(seconds)) and 0 <= seconds < 86_400:
        result["audio_seconds"] = round(float(seconds), 3)
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
    for key in ("input_per_million", "output_per_million", "per_hour"):
        if key == "per_hour" and key not in provenance:
            continue  # an audio rate only on an audio row: a token row keeps its shape
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
        AIOutputInvalid: "output_invalid",
        AIProviderResponseInvalid: "provider_response_invalid",
        AIProviderTimeout: "provider_timeout",
        AIProviderUnavailable: "provider_unavailable",
        AIProviderError: "provider_error",
    }
    for error_type, label in names.items():
        if isinstance(error, error_type):
            return label
    return "operation_failed"


_ROUTER_TIERS = frozenset({"local", "free", "paid"})
_ROUTER_PHASES = frozenset({"pool", "escalation"})
_HTTP_STATUS_CLASSES = frozenset({"401", "402", "403", "429", "4xx", "5xx"})


def http_status_class(status: object) -> str | None:
    """The coarse class of an HTTP status for telemetry: the codes a router acts on, else 4xx / 5xx."""

    if type(status) is not int:
        return None
    if status in (401, 402, 403, 429):
        return str(status)
    if 400 <= status < 500:
        return "4xx"
    if 500 <= status < 600:
        return "5xx"
    return None


def _router_telemetry(value: dict[str, Any]) -> dict[str, Any]:
    """The AI Cost Router's fields (D-195). Added only when present; each is a closed vocabulary or a small
    pattern, so no word, prompt or URL can ride along."""

    extra: dict[str, Any] = {}
    tier, phase = value.get("tier"), value.get("phase")
    if "tier" in value:
        extra["tier"] = tier if tier in _ROUTER_TIERS else None
    if "phase" in value:
        extra["phase"] = phase if phase in _ROUTER_PHASES else None
    if "attempt" in value:
        attempt = value.get("attempt")
        extra["attempt"] = attempt if type(attempt) is int and 1 <= attempt <= 20 else None
    if "fallback_reason" in value:
        reason = value.get("fallback_reason")
        extra["fallback_reason"] = reason if isinstance(reason, str) and re.fullmatch(r"[a-z][a-z_]{0,39}", reason) else None
    if "http_status_class" in value:
        status_class = value.get("http_status_class")
        extra["http_status_class"] = status_class if status_class in _HTTP_STATUS_CLASSES else None
    if "router_version" in value:
        version = value.get("router_version")
        extra["router_version"] = version if isinstance(version, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,19}", version) else None
    return extra


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
    # PR-MON-6 §8: True only for a request that was actually sent to a provider (success or failure). A rung skipped
    # before any outbound request (budget, unfunded, cooling down) or a call refused before sending is never billable.
    if value.get("billable_attempt") is True:
        result["billable_attempt"] = True
    # D-219: the tier in force when the call was recorded (cost.free_tier.<provider>); never rewritten afterwards.
    if type(value.get("free_tier")) is bool:
        result["free_tier"] = value["free_tier"]
    # D-221: the environment that wrote the event (the provider key is shared by many); a short token or absent.
    environment = value.get("environment")
    if isinstance(environment, str) and re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,39}", environment):
        result["environment"] = environment
    # PR-MON-7 §4.4: an estimate of whether provider credits covered the call; never a cash fact.
    if value.get("cost_coverage") in {"provider_credit_estimated", "cash", "unknown"}:
        result["cost_coverage"] = value["cost_coverage"]
    # PR BZ: the failure's class for provider health (ai/health_signal.py), a closed vocabulary decided from the
    # provider's answer when it was recorded; the answer's own words are never kept.
    if outcome == "failure" and value.get("failure_class") in _FAILURE_CLASSES:
        result["failure_class"] = value["failure_class"]
    # A chain's closing row repeats a failure each rung already recorded; health does not count it twice.
    if value.get("chain_summary") is True:
        result["chain_summary"] = True
    switch = _provider_switch(value.get("provider_switch"))
    if switch is not None:
        result["provider_switch"] = switch
    result.update(_router_telemetry(value))
    return result


_PROVIDER_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}")
_SWITCH_REASONS = frozenset({"spend_cap", "rate_limit", "auth", "unconfigured", "server", "timeout", "schema", "other",
                             "privacy", "budget", "unfunded"})


def _provider_switch(value: object) -> dict[str, Any] | None:
    """PR BZ: the router moved from the first rung to another (from, to, reason, trigger) - provider ids and closed
    words only, so nothing a learner wrote can ride along."""

    if not isinstance(value, dict):
        return None
    source, target = value.get("from"), value.get("to")
    if not isinstance(source, str) or not _PROVIDER_ID.fullmatch(source):
        return None
    if target is not None and (not isinstance(target, str) or not _PROVIDER_ID.fullmatch(target)):
        target = None
    reason = value.get("reason") if value.get("reason") in _SWITCH_REASONS else "other"
    trigger = value.get("trigger") if value.get("trigger") in {"down", "failed", "refused"} else "failed"
    return {"from": source, "to": target, "reason": reason, "trigger": trigger}


_FAILURE_CLASSES = frozenset({"spend_cap", "rate_limit", "auth", "unconfigured", "server", "timeout", "schema", "other",
                              "not_counted"})


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
