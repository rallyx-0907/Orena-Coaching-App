from __future__ import annotations

import pytest

from writing_coach.ai.base import (
    AICapabilityDisabled,
    AICapabilityError,
    AICapabilityNotConfigured,
    AICapabilityUnsupported,
    AIModelUnavailable,
    AIProviderError,
    AIProviderUnavailable,
    AIProviderUnsupportedOperation,
)
from writing_coach.ai.capabilities import (
    AIFallbackPolicy,
    AIOperation,
    all_capabilities,
    get_capability,
    require_capability,
)
from writing_coach.ai.providers import get_provider_definition, provider_definitions


EXPECTED_KEYS = {
    "writing_evaluator",
    "writing_linguistic",
    "reading_generator",
    "writing_task_generator",
    "writing_improver",
    "learner_dictionary",
    "learner_translation",
    "grammar_lesson_generator",
    "reading_evaluator",
    "text_discussion",
    "speech_asr",
    "pronunciation_evaluator",
    "speaking_evaluator",
}


def test_capability_catalog_contains_exactly_the_required_unique_keys() -> None:
    definitions = all_capabilities()
    keys = [definition.key for definition in definitions]

    assert set(keys) == EXPECTED_KEYS
    assert len(keys) == len(set(keys)) == len(EXPECTED_KEYS)
    assert get_capability(" WRITING_EVALUATOR ") == get_capability("writing_evaluator")
    assert get_capability("unknown_capability") is None
    with pytest.raises(AICapabilityUnsupported):
        require_capability("unknown_capability")


def test_reading_evaluator_remains_deterministic_and_not_configurable() -> None:
    definition = require_capability("reading_evaluator")

    assert definition.operation is AIOperation.DETERMINISTIC
    assert definition.provider_backed is False
    assert definition.configurable is False
    assert definition.implemented is True
    assert definition.allowed_fallback_policies == frozenset({AIFallbackPolicy.NONE})


def test_speech_capabilities_are_reserved_not_implemented() -> None:
    for key, operation in {
        "speech_asr": AIOperation.SPEECH_RECOGNITION,
        "pronunciation_evaluator": AIOperation.PRONUNCIATION_EVALUATION,
        "speaking_evaluator": AIOperation.SPEAKING_EVALUATION,
    }.items():
        definition = require_capability(key)
        assert definition.operation is operation
        assert definition.provider_backed is True
        assert definition.configurable is False
        assert definition.implemented is False


def test_static_text_provider_definitions_need_no_credentials_or_network(monkeypatch) -> None:
    for variable in (
        "OLLAMA_URL",
        "OLLAMA_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "GROQ_API_KEY",
        "GROQ_BASE_URL",
    ):
        monkeypatch.delenv(variable, raising=False)

    definitions = provider_definitions()
    assert {definition.id for definition in definitions} == {
        "ollama",
        "openai",
        "deepseek",
        "groq",
        "gemini",
    }

    speech_operations = {
        AIOperation.SPEECH_RECOGNITION,
        AIOperation.PRONUNCIATION_EVALUATION,
        AIOperation.SPEAKING_EVALUATION,
    }
    for definition in definitions:
        assert definition.supports(AIOperation.STRUCTURED_TEXT_GENERATION)
        assert definition.supported_operations.isdisjoint(speech_operations)
        assert "temperature" in definition.supported_option_keys
        assert get_provider_definition(definition.id) is definition


def test_capabilities_are_product_wide_and_only_reviewed_generators_allow_fallback() -> None:
    definitions = all_capabilities()
    assert all(definition.language_overrides_allowed is False for definition in definitions)
    assert not any(definition.key.endswith(("_en", "_zh")) for definition in definitions)

    allowed = {
        definition.key
        for definition in definitions
        if AIFallbackPolicy.DETERMINISTIC_FALLBACK in definition.allowed_fallback_policies
    }
    assert allowed == {
        "reading_generator",
        "writing_task_generator",
        "grammar_lesson_generator",
    }


def test_capability_and_provider_error_taxonomy_is_explicit() -> None:
    assert issubclass(AICapabilityDisabled, AICapabilityError)
    assert issubclass(AICapabilityNotConfigured, AICapabilityError)
    assert issubclass(AICapabilityUnsupported, AICapabilityError)
    assert issubclass(AIProviderUnsupportedOperation, AICapabilityUnsupported)
    assert issubclass(AIModelUnavailable, AIProviderUnavailable)
    assert issubclass(AIProviderUnavailable, AIProviderError)
