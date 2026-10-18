"""Immutable, product-wide AI capability contracts.

This module deliberately contains no persistence or runtime-selection logic.
Later control-plane slices use these definitions to validate configuration and
route requests without duplicating capabilities by learning language.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from writing_coach.ai.base import AICapabilityUnsupported


class AIOperation(StrEnum):
    """The operation a provider must explicitly support for a capability."""

    STRUCTURED_TEXT_GENERATION = "structured_text_generation"
    DETERMINISTIC = "deterministic"
    SPEECH_RECOGNITION = "speech_recognition"
    PRONUNCIATION_EVALUATION = "pronunciation_evaluation"
    SPEAKING_EVALUATION = "speaking_evaluation"
    # Orena Intelligence (D-085).
    AGENT_TURN = "agent_turn"  # streaming turn with native tool calls
    CONVERSATIONAL_SPEECH = "conversational_speech"  # speech-to-speech session
    TEXT_TO_SPEECH = "text_to_speech"


class AIFallbackPolicy(StrEnum):
    """Reviewed fallback policies a capability may opt into."""

    NONE = "none"
    DETERMINISTIC_FALLBACK = "deterministic_fallback"


@dataclass(frozen=True)
class AICapabilityDefinition:
    """Static capability metadata; operator configuration is stored elsewhere."""

    key: str
    operation: AIOperation
    provider_backed: bool
    configurable: bool
    implemented: bool
    allowed_fallback_policies: frozenset[AIFallbackPolicy]
    language_overrides_allowed: bool = False
    # What a request to this capability may carry (AI Cost Router, D-195). `learner_text` is the conservative
    # default: a free tier or any provider that may log prompts is refused for it. `public_reference` is a word or
    # phrase taken from published content, with no learner-authored text.
    input_class: str = "learner_text"
    # Not part of the legacy-to-capability activation set: switched on by the operator, ships disabled.
    opt_in: bool = False
    # Tier rule (AI Cost Router, D-195 amendment 2026-10-14): the primary may be a free or local model only. The
    # standby may be too, or a cheap paid model when `paid_standby_cap_policy` names a per-capability daily spend
    # cap (a `writing_coach.policies` key) that is above zero. Escalation and premium tiers stay refused.
    free_primary_only: bool = False
    paid_standby_cap_policy: str = ""
    # The only paid (provider, model) pairs that standby may be: cheap, non-reasoning and priced in the catalogue.
    paid_standby_models: frozenset[tuple[str, str]] = frozenset()
    # PR-MON-7 (design revision 2.1 §4.2): the (provider, model) pairs reviewed as this capability's primary when it is
    # routed (`ORENA_CAPABILITY_ROUTING`). Empty = the capability cannot be routed; it stays on the legacy selection.
    # No model is reviewed yet (human decisions H7-2, H7-8).
    reviewed_primary_models: frozenset[tuple[str, str]] = frozenset()


INPUT_CLASSES = frozenset({"public_reference", "published_content", "learner_text"})
_CAPABILITY_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def _definition(
    key: str,
    *,
    operation: AIOperation,
    provider_backed: bool,
    configurable: bool,
    implemented: bool,
    fallback_policies: frozenset[AIFallbackPolicy] = frozenset({AIFallbackPolicy.NONE}),
    input_class: str = "learner_text",
    opt_in: bool = False,
    free_primary_only: bool = False,
    paid_standby_cap_policy: str = "",
    paid_standby_models: frozenset[tuple[str, str]] = frozenset(),
    reviewed_primary_models: frozenset[tuple[str, str]] = frozenset(),
) -> AICapabilityDefinition:
    if input_class not in INPUT_CLASSES:
        raise ValueError(f"Invalid input class for {key!r}: {input_class!r}")
    if not _CAPABILITY_KEY.fullmatch(key):
        raise ValueError(f"Invalid AI capability key: {key!r}")
    if not provider_backed and operation is not AIOperation.DETERMINISTIC:
        raise ValueError(f"Non-provider capability {key!r} must be deterministic.")
    if configurable and not provider_backed:
        raise ValueError(f"Non-provider capability {key!r} cannot be configurable.")
    return AICapabilityDefinition(
        key=key,
        operation=operation,
        provider_backed=provider_backed,
        configurable=configurable,
        implemented=implemented,
        allowed_fallback_policies=fallback_policies,
        input_class=input_class,
        opt_in=opt_in,
        free_primary_only=free_primary_only,
        paid_standby_cap_policy=paid_standby_cap_policy,
        paid_standby_models=paid_standby_models,
        reviewed_primary_models=reviewed_primary_models,
    )


_DETERMINISTIC_FALLBACK = frozenset(
    {AIFallbackPolicy.NONE, AIFallbackPolicy.DETERMINISTIC_FALLBACK}
)
_DEFINITIONS = (
    _definition(
        "writing_evaluator",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
    ),
    # Segmentation and part-of-speech tagging are a solved deterministic problem
    # (jieba, NLTK). This capability was provider-backed until the local tagger
    # replaced it; it stays in the catalog as a named workload, the way
    # reading_evaluator does, but nothing routes it to a provider.
    _definition(
        "writing_linguistic",
        operation=AIOperation.DETERMINISTIC,
        provider_backed=False,
        configurable=False,
        implemented=True,
    ),
    _definition(
        "reading_generator",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
        fallback_policies=_DETERMINISTIC_FALLBACK,
    ),
    _definition(
        "writing_task_generator",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
        fallback_policies=_DETERMINISTIC_FALLBACK,
    ),
    _definition(
        "writing_improver",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
    ),
    _definition(
        "learner_dictionary",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
    ),
    _definition(
        "learner_translation",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
    ),
    # AI Cost Router slice 1 (D-195): the basic tap's last layer. A word or phrase of at most three words, never the
    # sentence; ships disabled and is switched on by the operator, so it is outside the activation set.
    _definition(
        "word_translation",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
        fallback_policies=_DETERMINISTIC_FALLBACK,
        input_class="public_reference",
        opt_in=True,
        free_primary_only=True,
        paid_standby_cap_policy="word_translation.daily_spend_cap_usd",
        # Owner decision 2026-10-14: a cheap paid standby, behind a daily cap. Groq's non-reasoning 70B (the 8B
        # instant model is enterprise-only, "contact sales", on Groq's public models page).
        paid_standby_models=frozenset({("groq", "llama-3.3-70b-versatile")}),
    ),
    # D-224 (PROPOSED): the platform router behind media translation and transcript correction. Groq stays the first
    # engine of both; these capabilities are what a batch is sent to when Groq cannot take it (a long rate limit, a
    # spent daily quota, a request that cannot shrink, a provider fault, or no Groq credential). Opt-in, like
    # `word_translation`: no row is required, so nothing changes until the operator picks a provider, model and backup in
    # Admin. A learner's private import is learner content (D-104), so the default `learner_text` class stays: no free tier and no
    # prompt-logging provider (OpenRouter) is accepted until the owner decides otherwise (D-224 open question).
    _definition(
        "media_translation",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
        opt_in=True,
    ),
    _definition(
        "media_transcript_correction",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
        opt_in=True,
    ),
    _definition(
        "grammar_lesson_generator",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
        fallback_policies=_DETERMINISTIC_FALLBACK,
    ),
    # D-072.2: the learner's questions about a whole text. Provider-backed and
    # configurable like every other tutor answer; no deterministic fallback,
    # because a canned reply to a learner's own question would be worse than
    # saying the tutor is unavailable and offering a retry.
    _definition(
        "text_discussion",
        operation=AIOperation.STRUCTURED_TEXT_GENERATION,
        provider_backed=True,
        configurable=True,
        implemented=True,
    ),
    _definition(
        "reading_evaluator",
        operation=AIOperation.DETERMINISTIC,
        provider_backed=False,
        configurable=False,
        implemented=True,
    ),
    _definition(
        "speech_asr",
        operation=AIOperation.SPEECH_RECOGNITION,
        provider_backed=True,
        configurable=False,
        implemented=False,
    ),
    _definition(
        "pronunciation_evaluator",
        operation=AIOperation.PRONUNCIATION_EVALUATION,
        provider_backed=True,
        configurable=False,
        implemented=False,
    ),
    _definition(
        "speaking_evaluator",
        operation=AIOperation.SPEAKING_EVALUATION,
        provider_backed=True,
        configurable=False,
        implemented=False,
    ),
    # Orena Intelligence (D-085), reserved like the speech keys: defined, not
    # configurable, no fallback. Until a reviewed activation makes them
    # configurable, an agent turn routes through the legacy active selection
    # like every learner call (human ruling 2026-09-27).
    _definition(
        "agent_turn_fast",
        operation=AIOperation.AGENT_TURN,
        provider_backed=True,
        configurable=False,
        implemented=False,
    ),
    _definition(
        "agent_turn_deep",
        operation=AIOperation.AGENT_TURN,
        provider_backed=True,
        configurable=False,
        implemented=False,
    ),
    _definition(
        "conversational_speech",
        operation=AIOperation.CONVERSATIONAL_SPEECH,
        provider_backed=True,
        configurable=False,
        implemented=False,
    ),
    _definition(
        "text_to_speech",
        operation=AIOperation.TEXT_TO_SPEECH,
        provider_backed=True,
        configurable=False,
        implemented=False,
    ),
)

if len({definition.key for definition in _DEFINITIONS}) != len(_DEFINITIONS):
    raise RuntimeError("AI capability catalog contains duplicate keys.")

CAPABILITY_CATALOG: Mapping[str, AICapabilityDefinition] = MappingProxyType(
    {definition.key: definition for definition in _DEFINITIONS}
)


def normalize_capability_key(key: str) -> str:
    """Normalize a caller supplied key without inventing aliases or defaults."""

    normalized = str(key or "").strip().casefold()
    if not _CAPABILITY_KEY.fullmatch(normalized):
        raise AICapabilityUnsupported(f"Unknown AI capability: {key!r}")
    return normalized


def all_capabilities() -> tuple[AICapabilityDefinition, ...]:
    """Return catalog definitions in the stable product-owned order."""

    return _DEFINITIONS


def configurable_provider_capabilities() -> tuple[AICapabilityDefinition, ...]:
    """Return the current capabilities that require explicit provider config."""

    return tuple(
        definition
        for definition in _DEFINITIONS
        if definition.implemented
        and definition.provider_backed
        and definition.configurable
    )


def activation_capabilities() -> tuple[AICapabilityDefinition, ...]:
    """The configurable capabilities the legacy-to-capability activation requires a row for.

    Opt-in capabilities (`word_translation`) ship disabled and are not part of that gate."""

    return tuple(definition for definition in configurable_provider_capabilities() if not definition.opt_in)


def get_capability(key: str) -> AICapabilityDefinition | None:
    """Return an exact capability match; unknown values never select a default."""

    try:
        normalized = normalize_capability_key(key)
    except AICapabilityUnsupported:
        return None
    return CAPABILITY_CATALOG.get(normalized)


def require_capability(key: str) -> AICapabilityDefinition:
    definition = get_capability(key)
    if definition is None:
        raise AICapabilityUnsupported(f"Unknown AI capability: {key!r}")
    return definition
