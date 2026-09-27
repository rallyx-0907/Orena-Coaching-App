"""Versioned, code-owned token pricing evidence for operator observation.

This catalog is deliberately exact-match: an unknown provider/model is
reported as unpriced rather than inheriting a nearby model's rate.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any


PRICING_CATALOG_VERSION = "2026-09-28.v1"
MAX_PRICED_TOKENS = 1_000_000_000


@dataclass(frozen=True)
class TokenPricing:
    provider: str
    model: str
    currency: str
    input_per_million: float
    output_per_million: float


_CATALOG = MappingProxyType({
    ("openai", "gpt-4o-mini"): TokenPricing("openai", "gpt-4o-mini", "USD", 0.15, 0.60),
    ("openai", "gpt-4o"): TokenPricing("openai", "gpt-4o", "USD", 2.50, 10.00),
    ("deepseek", "deepseek-chat"): TokenPricing("deepseek", "deepseek-chat", "USD", 0.27, 1.10),
    ("deepseek", "deepseek-reasoner"): TokenPricing("deepseek", "deepseek-reasoner", "USD", 0.55, 2.19),
    ("groq", "llama-3.3-70b-versatile"): TokenPricing("groq", "llama-3.3-70b-versatile", "USD", 0.59, 0.79),
    # Published paid-tier text rate, ai.google.dev/gemini-api/docs/pricing, read 2026-09-27.
    ("gemini", "gemini-3.5-flash-lite"): TokenPricing("gemini", "gemini-3.5-flash-lite", "USD", 0.30, 2.50),
})


def resolve_token_pricing(provider: object, model: object) -> TokenPricing | None:
    """Resolve only an exact catalog entry; never infer or fall back."""

    key = (str(provider or "").strip().casefold(), str(model or "").strip())
    return _CATALOG.get(key)


def estimate_token_cost(provider: object, model: object, usage: object) -> dict[str, Any]:
    """Return an explicit cost state and event-time pricing provenance.

    Estimates require both prompt and completion counts. Total-only provider
    usage remains unknown/partial rather than being split heuristically.
    """

    provider_id = str(provider or "").strip().casefold() or None
    model_id = str(model or "").strip() or None
    pricing = resolve_token_pricing(provider_id, model_id)
    source = usage if isinstance(usage, dict) else {}
    prompt = source.get("prompt_tokens")
    completion = source.get("completion_tokens")
    has_prompt = type(prompt) is int and prompt >= 0
    has_completion = type(completion) is int and completion >= 0
    if not has_prompt and not has_completion:
        usage_state = "unknown"
        reason = "usage_unreported"
    elif not (has_prompt and has_completion):
        usage_state = "partial"
        reason = "usage_partial"
    elif prompt > MAX_PRICED_TOKENS or completion > MAX_PRICED_TOKENS:
        usage_state = "unknown"
        reason = "usage_out_of_range"
    else:
        usage_state = "complete"
        reason = None
    if pricing is None:
        state = "unpriced"
        reason = "model_not_cataloged"
    elif usage_state != "complete":
        state = usage_state
    else:
        state = "estimated"
    result: dict[str, Any] = {
        "state": state,
        "currency": pricing.currency if pricing is not None and state == "estimated" else None,
        "amount": None,
        "provenance": {
            "catalog_version": PRICING_CATALOG_VERSION,
            "provider": pricing.provider if pricing is not None else provider_id,
            "model": pricing.model if pricing is not None else model_id,
            "input_per_million": pricing.input_per_million if pricing is not None else None,
            "output_per_million": pricing.output_per_million if pricing is not None else None,
            "reason": reason,
        },
    }
    if state == "estimated" and pricing is not None:
        amount = (prompt * pricing.input_per_million + completion * pricing.output_per_million) / 1_000_000
        result["amount"] = round(amount, 8) if math.isfinite(amount) else None
    return result


def pricing_catalog() -> tuple[TokenPricing, ...]:
    """Expose catalog entries for offline governance/inspection only."""

    return tuple(_CATALOG.values())
