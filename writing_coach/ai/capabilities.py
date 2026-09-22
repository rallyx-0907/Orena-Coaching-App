"""Immutable, product-wide AI capability contracts.

This module deliberately contains no persistence or runtime-selection logic.
Later control-plane slices use these definitions to validate configuration and
route requests without duplicating capabilities by learning language.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from writing_coach.ai.base import AICapabilityUnsupported


class AIOperation(StrEnum):
    """The operation a provider must explicitly support for a capability."""

    STRUCTURED_TEXT_GENERATION = "structured_text_generation"
    DETERMINISTIC = "deterministic"
    SPEECH_RECOGNITION = "speech_recognition"
    PRONUNCIATION_EVALUATION = "pronunciation_evaluation"
    SPEAKING_EVALUATION = "speaking_evaluation"


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


_CAPABILITY_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def _definition(
    key: str,
    *,
    operation: AIOperation,
    provider_backed: bool,
    configurable: bool,
    implemented: bool,
    fallback_policies: frozenset[AIFallbackPolicy] = frozenset({AIFallbackPolicy.NONE}),
) -> AICapabilityDefinition:
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
