"""Versioned, code-owned token pricing evidence for operator observation.

This catalog is deliberately exact-match: an unknown provider/model is
reported as unpriced rather than inheriting a nearby model's rate.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any


PRICING_CATALOG_VERSION = "2026-10-14.v7"
MAX_PRICED_TOKENS = 1_000_000_000


@dataclass(frozen=True)
class TokenPricing:
    provider: str
    model: str
    currency: str
    input_per_million: float
    output_per_million: float
    # Why a rate is what it is, when that is a fact about the account rather than the model (a free plan).
    note: str = ""


_CATALOG = MappingProxyType({
    ("openai", "gpt-4o-mini"): TokenPricing("openai", "gpt-4o-mini", "USD", 0.15, 0.60),
    ("openai", "gpt-4o"): TokenPricing("openai", "gpt-4o", "USD", 2.50, 10.00),
    ("deepseek", "deepseek-chat"): TokenPricing("deepseek", "deepseek-chat", "USD", 0.27, 1.10),
    ("deepseek", "deepseek-reasoner"): TokenPricing("deepseek", "deepseek-reasoner", "USD", 0.55, 2.19),
    ("groq", "llama-3.3-70b-versatile"): TokenPricing("groq", "llama-3.3-70b-versatile", "USD", 0.59, 0.79),
    # Media pre-translation (D-168): published rate, console.groq.com/docs/model/openai/gpt-oss-120b, read 2026-10-09
    # (input 0.15, output 0.60 per million; the cached-input rate 0.075 is not modelled, so this never understates).
    ("groq", "openai/gpt-oss-120b"): TokenPricing("groq", "openai/gpt-oss-120b", "USD", 0.15, 0.60),
    # Word translation standby (D-195 amendment 2026-10-14): a Groq FREE-PLAN model, recorded at zero. source:
    # owner-confirmed Groq free plan (no billing), 2026-10-14; the model is listed as active on the public models
    # page https://console.groq.com/docs/models (its paid price there is "contact sales"). If billing is ever added to
    # the Groq account this call becomes billable while still recorded as 0: revisit this entry (and the cap in
    # `word_translation.daily_spend_cap_usd`) first.
    ("groq", "llama-3.1-8b-instant"): TokenPricing(
        "groq", "llama-3.1-8b-instant", "USD", 0.0, 0.0,
        note="owner-confirmed Groq free plan (no billing), 2026-10-14; https://console.groq.com/docs/models",
    ),
    # Probed live 2026-10-14 (:8021): the Groq key's catalogue lists only allam-2-7b, openai/gpt-oss-120b,
    # openai/gpt-oss-20b and qwen/qwen3.8-27b, so `llama-3.1-8b-instant` above is NOT available to this key (HTTP 409
    # model_unavailable). `qwen/qwen3.8-27b` answered en->vi "infrastructure" and zh->vi in 0.3-0.7 s: the standby to use.
    ("groq", "qwen/qwen3.8-27b"): TokenPricing(
        "groq", "qwen/qwen3.8-27b", "USD", 0.0, 0.0,
        note="owner-confirmed Groq free plan (no billing), 2026-10-14; same revisit rule as llama-3.1-8b-instant",
    ),
    # Published paid-tier text rate, ai.google.dev/gemini-api/docs/pricing, read 2026-09-27.
    ("gemini", "gemini-3.5-flash-lite"): TokenPricing("gemini", "gemini-3.5-flash-lite", "USD", 0.30, 2.50),
    # AI Cost Router (D-195): pinned OpenRouter ":free" models, an explicit zero rate so a free call is "estimated at 0"
    # and never counted as unpriced by the daily spend ledger. VERIFIED 2026-10-14 against the public catalogue
    # https://openrouter.ai/api/v1/models (no key): all three ids are listed with the ":free" suffix. A model is only
    # usable once it is listed here (providers.check_model_allowed); to offer another free id, add its entry.
    #   gemma-4-31b-it   primary
    #   gemma-4-26b-a4b-it   standby: different weights, same family
    #   nemotron-3-super-120b-a12b   a second-vendor option
    # Probed live 2026-10-14 (:8021, en->vi "poetry" and zh->vi, reasoning switched off, catalogue
    # https://openrouter.ai/api/v1/models): dots-3-note-preview and nemotron-3.5-lightning also answered a valid
    # short gloss, so they are pinned below. The gemma models answered HTTP 429 from their upstream on every probe.
    ("openrouter", "google/gemma-4-31b-it:free"): TokenPricing("openrouter", "google/gemma-4-31b-it:free", "USD", 0.0, 0.0),
    ("openrouter", "google/gemma-4-26b-a4b-it:free"): TokenPricing(
        "openrouter", "google/gemma-4-26b-a4b-it:free", "USD", 0.0, 0.0
    ),
    ("openrouter", "nvidia/nemotron-3-super-120b-a12b:free"): TokenPricing(
        "openrouter", "nvidia/nemotron-3-super-120b-a12b:free", "USD", 0.0, 0.0
    ),
    ("openrouter", "dots-studio/dots-3-note-preview:free"): TokenPricing(
        "openrouter", "dots-studio/dots-3-note-preview:free", "USD", 0.0, 0.0
    ),
    ("openrouter", "nvidia/nemotron-3.5-lightning:free"): TokenPricing(
        "openrouter", "nvidia/nemotron-3.5-lightning:free", "USD", 0.0, 0.0
    ),
})


@dataclass(frozen=True)
class AudioPricing:
    """A per-hour audio rate with the provider's billing rules (minimum per request, rounding increment)."""

    provider: str
    model: str
    currency: str
    per_hour: float
    minimum_seconds: float
    increment_seconds: float
    source: str


_AUDIO_CATALOG = MappingProxyType({
    # Groq ASR model guide (groq.com/GroqDocs, read 2026-10-04): $0.04 per audio hour, 10 s minimum per request.
    ("groq", "whisper-large-v3-turbo"): AudioPricing("groq", "whisper-large-v3-turbo", "USD", 0.04, 10.0, 1.0,
                                                     "groq-asr-model-guide-2026-10-04"),
    ("groq", "whisper-large-v3"): AudioPricing("groq", "whisper-large-v3", "USD", 0.111, 10.0, 1.0,
                                               "groq-asr-model-guide-2026-10-04"),
    # Azure Speech pronunciation assessment, standard real-time: $1.32 per audio hour, billed per second
    # (Microsoft Learn Q&A 5608069, Nov 2025, US East). Not the invoice: check it against the Azure bill.
    ("azure-speech", "pronunciation-assessment"): AudioPricing("azure-speech", "pronunciation-assessment", "USD",
                                                               1.32, 0.0, 1.0, "ms-learn-qa-5608069-2025-11"),
    # Gemini Live, a voice session's wall-clock time (agent/voice_session.py, R28): about $0.036 a minute, the list
    # price AGENT_SPEC §41 carries (AGENT_VOICE_SLICE4 §2.2). Unverified: check it against the Gemini bill (Q11).
    ("gemini", "gemini-3.8-live"): AudioPricing("gemini", "gemini-3.8-live", "USD", 2.16, 0.0, 1.0,
                                                "agent-spec-41-list-price-unverified"),
})


def estimate_audio_cost(provider: object, model: object, audio_seconds: object) -> dict[str, Any]:
    """The cost of one audio request: its seconds billed by the provider's rules, at the catalog rate.

    Unknown duration or an uncatalogued model is said as such (`unknown`, `unpriced`), never priced as zero.
    """

    provider_id = str(provider or "").strip().casefold() or None
    model_id = str(model or "").strip() or None
    pricing = _AUDIO_CATALOG.get((provider_id or "", model_id or ""))
    known = type(audio_seconds) in {int, float} and math.isfinite(float(audio_seconds)) and 0 <= audio_seconds < 86_400
    state = "unpriced" if pricing is None else ("estimated" if known else "unknown")
    result: dict[str, Any] = {
        "state": state,
        "currency": pricing.currency if state == "estimated" else None,
        "amount": None,
        "provenance": {
            "catalog_version": PRICING_CATALOG_VERSION,
            "provider": pricing.provider if pricing else provider_id,
            "model": pricing.model if pricing else model_id,
            "per_hour": pricing.per_hour if pricing else None,
            "reason": None if state == "estimated" else ("model_not_cataloged" if pricing is None else "duration_unknown"),
        },
    }
    if state == "estimated" and pricing is not None:
        seconds = max(float(audio_seconds), pricing.minimum_seconds)
        billed = math.ceil(seconds / pricing.increment_seconds) * pricing.increment_seconds
        result["amount"] = round(billed * pricing.per_hour / 3600, 8)
    return result


def audio_pricing_catalog() -> tuple[AudioPricing, ...]:
    return tuple(_AUDIO_CATALOG.values())


def resolve_token_pricing(provider: object, model: object) -> TokenPricing | None:
    """Resolve only an exact catalog entry; never infer or fall back."""

    key = (str(provider or "").strip().casefold(), str(model or "").strip())
    return _CATALOG.get(key)


def is_free_model(provider: object, model: object) -> bool:
    """A model that costs nothing and may log prompts: a zero-rate catalogue entry, or an OpenRouter ":free" id."""

    pricing = resolve_token_pricing(provider, model)
    if pricing is not None:
        return pricing.input_per_million == 0 and pricing.output_per_million == 0
    return str(provider or "").strip().casefold() == "openrouter" and str(model or "").strip().endswith(":free")


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
    free = pricing is not None and pricing.input_per_million == 0 and pricing.output_per_million == 0
    if pricing is None:
        state = "unpriced"
        reason = "model_not_cataloged"
    elif free:
        # A zero rate is the same whatever was counted: free is "estimated at 0", never "unknown" (which the
        # spend ledger would charge as an unpriced call).
        state = "estimated"
        reason = None
        usage_state = "complete"
        prompt = completion = 0
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
