"""Media translation and transcript correction through the platform AI router (D-224, PROPOSED).

Groq stays the first engine of the media pipeline (`media_translation.GroqTranslationProvider`). These two adapters are
what a batch is sent to when Groq cannot take it, or the only engine when `MEDIA_TRANSLATION_PROVIDER=ai`. Each calls
`generate_structured` on its own capability (`media_translation`, `media_transcript_correction`), so the provider, model
and backup are what the operator picked in Admin, the stored credentials apply, and every call lands once in the shared
AI cost records and telemetry (the router writes them; nothing here does).

What this module does NOT do: book the media spend ledger (the pipeline does, from the usage reported here), choose when
to fall back (`media_translation.capacity_refusal`), or touch speech recognition (a later change).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from writing_coach import media_translation as mt
from writing_coach.media_translation import TranslationProviderError

_logger = logging.getLogger(__name__)

TRANSLATION_CAPABILITY = "media_translation"
CORRECTION_CAPABILITY = "media_transcript_correction"
# One call's HTTP timeout: the same bound a Groq request has.
ATTEMPT_TIMEOUT_SECONDS = 90.0
MAX_TRANSLATION_ANSWER_TOKENS = 8192
MIN_ANSWER_TOKENS = 400


CACHE_TTL_SECONDS = 30.0
_clock = time.monotonic
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, Any]] = {}


def reset_cache() -> None:
    """Forget the cached provider and capability lookups (tests; a change in Admin applies within CACHE_TTL_SECONDS)."""
    with _cache_lock:
        _cache.clear()


def _cached(key: str, load: Any) -> Any:
    """`load()` at most once per CACHE_TTL_SECONDS: building the providers decrypts every stored credential, and a batch
    asks many times. A load that raises is not cached."""
    now = _clock()
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None and hit[0] > now:
            return hit[1]
    value = load()
    with _cache_lock:
        _cache[key] = (now + CACHE_TTL_SECONDS, value)
    return value


def _providers() -> dict[str, Any]:
    def load() -> dict[str, Any]:
        from writing_coach.ai import platform

        return platform.providers()

    return _cached("providers", load)


def groq_credentials(*, strict: bool = False) -> tuple[str, str]:
    """(api key, base URL) of Groq for the media pipeline: the key saved in Admin first, else `GROQ_API_KEY`, exactly the
    order `ai/providers.py` uses (D-037, D-224); a stored credential with no key means the environment's. Looked up at
    most every CACHE_TTL_SECONDS, so a key saved or deleted in Admin applies without a restart. An unreadable store is
    logged (the error class only) and the environment answers; with `strict` and no environment key it raises instead,
    so a start never silently chooses another engine because a read failed. The key is never logged here."""
    env_key = os.getenv("GROQ_API_KEY", "").strip()
    env_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    try:
        item = _providers().get("groq")
    except Exception as exc:  # noqa: BLE001
        if strict and not env_key:
            raise
        _logger.warning("The Admin-stored Groq credential could not be read (%s); the environment key applies.",
                        type(exc).__name__)
        return env_key, env_url
    if item is None:
        return env_key, env_url
    return (str(getattr(item, "api_key", "") or "").strip() or env_key,
            str(getattr(item, "base_url", "") or "") or env_url)


def _load_target(capability_key: str) -> tuple[str, str] | None:
    from writing_coach.ai import platform

    row = platform._installed_platform_repository().get_capability_config(capability_key)
    if row is None or not row.config.enabled:
        return None
    config = row.config
    if config.backup_provider is not None:
        # The spend check is made at the primary's price; a backup rung could answer dearer (D-224). Refused at save time
        # too (`NO_BACKUP_CAPABILITIES`); a row stored before that is not used.
        _logger.warning("Capability %s has a backup provider, which media capabilities do not take; it is not used.",
                        capability_key)
        return None
    if not getattr(_providers().get(config.provider), "configured", False):
        return None
    return config.provider, config.model


def capability_target(capability_key: str) -> tuple[str, str] | None:
    """The (provider, model) the operator configured for this capability, or None when there is nothing to ask: no row,
    disabled, a backup configured, or its provider has no credential. Configuration only, no network; cached briefly."""
    try:
        return _cached(f"target:{capability_key}", lambda: _load_target(capability_key))
    except Exception as exc:  # noqa: BLE001 - an unreadable configuration is no fallback, never a failure of the pipeline
        _logger.warning("Capability %s could not be read (%s); no router fallback.", capability_key, type(exc).__name__)
        return None


def map_router_error(error: BaseException) -> TranslationProviderError:
    """A router or capability failure as the stable reason code the pipeline already understands. Only the class of the
    failure is kept: a provider's message can carry request detail, and nothing here may carry a credential."""
    from writing_coach.ai.base import (
        AICapabilityDisabled,
        AICapabilityNotConfigured,
        AIOutputInvalid,
        AIProviderTimeout,
    )

    name = type(error).__name__
    if isinstance(error, (AICapabilityNotConfigured, AICapabilityDisabled)):
        return TranslationProviderError(name, reason="not_configured")
    if isinstance(error, AIProviderTimeout):
        return TranslationProviderError(name, reason="provider_timeout")
    if isinstance(error, AIOutputInvalid):
        return TranslationProviderError(name, reason="malformed_result")
    return TranslationProviderError(name, reason="provider_error")


def _usage(result: Any) -> dict[str, int]:
    """The tokens the provider reported for one answer (thinking tokens counted with the completion, D-221)."""
    from writing_coach.ai.base import normalized_usage, reported_completion_tokens

    runtime = result.runtime if isinstance(getattr(result, "runtime", None), dict) else {}
    usage = normalized_usage(runtime)
    prompt = usage.get("prompt_tokens")
    completion = reported_completion_tokens(runtime)
    if type(prompt) is not int or completion is None:
        return {}
    return {"prompt_tokens": prompt, "completion_tokens": completion}


def _call(capability_key: str, messages: list[dict[str, str]], schema: dict[str, Any], max_tokens: int) -> Any:
    from writing_coach.ai.base import AICapabilityError, AIProviderError
    from writing_coach.ai.platform import generate_structured
    from writing_coach.billing.funding_context import FundingRequired

    try:
        # `capability_mode`: the capability's own configuration decides, whatever AI_RUNTIME_MODE is.
        result = generate_structured(
            messages=messages, schema=schema, max_output_tokens=max_tokens, temperature=0.0,
            capability_key=capability_key, capability_mode=True, attempt_timeout=ATTEMPT_TIMEOUT_SECONDS,
        )
    except (AICapabilityError, AIProviderError, FundingRequired) as exc:
        raise map_router_error(exc) from exc
    mt.report_usage(str(result.model or ""), _usage(result), provider=str(result.provider or "ai"))
    return result


class PlatformMediaTranslator:
    """`media_translation`: one structured router call per batch."""

    engine_id = "ai"

    @property
    def model_version(self) -> str:
        target = self.target()
        return target[1] if target else TRANSLATION_CAPABILITY

    @property
    def configured(self) -> bool:
        return self.target() is not None

    def target(self) -> tuple[str, str] | None:
        return capability_target(TRANSLATION_CAPABILITY)

    def translate_batch(self, source_language: str, target_language: str, segments: mt.TranslationBatch) -> dict[str, str]:
        target = self.target()
        if target is None:
            raise TranslationProviderError("media_translation is not configured.", reason="not_configured")
        wire, canonical_ids = mt._wire_segments(segments)
        max_tokens = max(MIN_ANSWER_TOKENS, min(MAX_TRANSLATION_ANSWER_TOKENS, mt.estimate_output_tokens(segments)))
        scope = mt.current_fallback_scope()
        if scope is None:
            # No media spend scope (an on-demand call, not the import pipeline): there is no ledger to check, and neither
            # capability has a daily cap of its own, so an uncapped paid call is refused (D-224).
            raise TranslationProviderError("media_translation needs a media spend scope.", reason="not_configured")
        scope.admit(target[0], target[1], max_tokens)    # the spend check, before every router call
        result = _call(
            TRANSLATION_CAPABILITY,
            [
                {"role": "system", "content": mt.TRANSLATION_SYSTEM_PROMPT},
                {"role": "user", "content": mt.translation_user_prompt(source_language, target_language, wire)},
            ],
            mt.TRANSLATION_SCHEMA, max_tokens,
        )
        translated = mt.parse_translation_rows(result.data, set(canonical_ids))
        if translated is None:
            raise TranslationProviderError("media_translation answered a different set of lines.", reason="malformed_result")
        return {canonical_ids[key]: value for key, value in translated.items()}


class PlatformMediaCorrector:
    """`media_transcript_correction`: one structured router call per correction batch.

    Returns what `GroqTranslationProvider.correct` returns, through the same answer checks (`parse_correction_rows`); the
    pipeline then applies its per-cue edit rules (`reject_cue_edit`) to it exactly as it does to Groq's. It does not
    check spend itself: the pipeline checks the ledger before it calls this."""

    engine_id = "ai"

    @property
    def model_version(self) -> str:
        target = self.target()
        return target[1] if target else CORRECTION_CAPABILITY

    @property
    def configured(self) -> bool:
        return self.target() is not None

    def target(self) -> tuple[str, str] | None:
        return capability_target(CORRECTION_CAPABILITY)

    def correction_output_ceiling(self) -> int:
        return mt.MAX_GROQ_MAX_COMPLETION_TOKENS

    def correct(self, *, language: str, cues: tuple[Any, ...], title: str = "", description: str = "") -> dict[str, object]:
        target = self.target()
        if target is None:
            raise TranslationProviderError("media_transcript_correction is not configured.", reason="not_configured")
        texts = tuple(str(getattr(cue, "text", "")) for cue in cues)
        if not texts or len(texts) > 24 or sum(len(text) for text in texts) > 6_000:
            raise TranslationProviderError("Transcript correction batch exceeds its bound.", reason="request_too_large")
        max_tokens = max(MIN_ANSWER_TOKENS, min(MAX_TRANSLATION_ANSWER_TOKENS, mt.correction_output_bound(texts)))
        scope = mt.current_fallback_scope()
        if scope is not None:
            scope.admit(target[0], target[1], max_tokens)
        result = _call(CORRECTION_CAPABILITY, mt.correction_messages(language, texts, title, description),
                       mt.CORRECTION_SCHEMA, max_tokens)
        return mt.parse_correction_rows(result.data, texts, provider=str(result.provider or "ai"), model=str(result.model or ""))
