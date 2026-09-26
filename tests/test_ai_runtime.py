from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import writing_coach.ai.platform as platform
from writing_coach.becoming_linguistics import (
    configure_becoming_linguistics,
    linguistic_annotations_for_essay,
)
from writing_coach.persistence.reading_evidence_repository import ReadingEvidenceError
from writing_coach.reading_comprehension import process_article
from writing_coach.ai.base import (
    AICapabilityError,
    AICapabilityConfigInvalid,
    AICapabilityDisabled,
    AICapabilityNotConfigured,
    AICapabilityUnsupported,
    AIResult,
)
from writing_coach.ai.config import CapabilityConfig
from writing_coach.persistence.platform_repository import CapabilityConfigRecord


@dataclass
class Repository:
    config: CapabilityConfig | None = None

    def initialize(self) -> None:
        pass

    def get_capability_config(self, key: str) -> CapabilityConfigRecord | None:
        return CapabilityConfigRecord(key, self.config) if self.config else None


@dataclass
class Provider:
    configured: bool = True
    id: str = "openai"
    name: str = "OpenAI"

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate_json_once(self, **kwargs: Any) -> AIResult:
        self.calls.append(kwargs)
        return AIResult(data={"ok": True}, provider=self.id, model=kwargs["model"], runtime={})

    generate_json = generate_json_once

    def discover_models_live(self) -> None:
        pytest.fail("learner runtime performed live model discovery")


def config(**overrides: Any) -> CapabilityConfig:
    values = {
        "enabled": True,
        "provider": "openai",
        "model": "capability-model",
        "temperature": 0.2,
        "fallback_policy": "none",
    }
    values.update(overrides)
    return CapabilityConfig(**values)


def install(monkeypatch: pytest.MonkeyPatch, repository: Repository, provider: Provider) -> None:
    monkeypatch.setattr(platform, "_platform_repository", repository)
    monkeypatch.setattr(platform, "providers", lambda: {"openai": provider})


def request(**kwargs: Any) -> AIResult:
    return platform.generate_structured(
        messages=[], schema={"type": "object"}, max_output_tokens=20, **kwargs
    )


def test_default_mode_remains_legacy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_RUNTIME_MODE", raising=False)
    legacy = Provider(id="legacy", name="Legacy")
    monkeypatch.setattr(platform, "active_selection", lambda: (legacy, "legacy-model"))

    result = request()

    assert result.model == "legacy-model"
    assert len(legacy.calls) == 1


def test_invalid_runtime_mode_fails_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_RUNTIME_MODE", "per_capability")

    with pytest.raises(platform.AICapabilityConfigInvalid):
        platform.runtime_mode()


def test_capability_mode_uses_only_exact_persisted_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    repository = Repository(config())
    selected = Provider()
    fallback = Provider(id="deepseek", name="DeepSeek")
    install(monkeypatch, repository, selected)
    monkeypatch.setattr(platform, "providers", lambda: {"openai": selected, "deepseek": fallback})
    monkeypatch.setattr(platform, "active_selection", lambda: pytest.fail("legacy routing used"))

    result = request(capability_key="writing_evaluator", temperature=0.9)

    assert result.model == "capability-model"
    assert selected.calls == [
        {
            "messages": [], "schema": {"type": "object"}, "model": "capability-model",
            "max_output_tokens": 20, "temperature": 0.2, "seed": None,
        }
    ]
    assert fallback.calls == []


@pytest.mark.parametrize(
    ("runtime_config", "capability_key", "error"),
    [
        (None, "writing_evaluator", AICapabilityNotConfigured),
        (config(enabled=False), "writing_evaluator", AICapabilityDisabled),
        (config(), "speech_asr", AICapabilityUnsupported),
        (config(), "unknown", AICapabilityUnsupported),
    ],
)
def test_capability_mode_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    runtime_config: CapabilityConfig | None,
    capability_key: str,
    error: type[Exception],
) -> None:
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    provider = Provider()
    install(monkeypatch, Repository(runtime_config), provider)
    monkeypatch.setattr(platform, "active_selection", lambda: pytest.fail("legacy routing used"))

    with pytest.raises(error):
        request(capability_key=capability_key)
    assert provider.calls == []


def test_malformed_persisted_config_fails_without_legacy_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MalformedRepository(Repository):
        def get_capability_config(self, key: str) -> CapabilityConfigRecord | None:
            raise AICapabilityConfigInvalid("malformed persisted config")

    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    provider = Provider()
    install(monkeypatch, MalformedRepository(), provider)
    monkeypatch.setattr(platform, "active_selection", lambda: pytest.fail("legacy routing used"))

    with pytest.raises(AICapabilityConfigInvalid, match="malformed persisted config"):
        request(capability_key="writing_evaluator")
    assert provider.calls == []


class SpecializedRepository:
    def __init__(self, language_code: str = "en") -> None:
        self.language_code = language_code

    def select_library_terms(self, limit: int) -> list[str]:
        return []

    def get_linguistic_essay(self, essay_id: int) -> dict[str, Any] | None:
        if essay_id != 1:
            return None
        return {
            "text": "I write." if self.language_code == "en" else "我写。",
            "language_code": self.language_code,
            "module_data_json": "{}",
        }

    def update_essay_module_data(self, essay_id: int, value: dict[str, Any]) -> None:
        self.module_data = value


ARTICLES = {
    "en": {"title": "Rain", "body": "The river rose overnight.", "language": "en", "effective_level": "B1"},
    "zh": {"title": "雨", "body": "河水一夜之间涨了。", "language": "zh", "effective_level": "HSK3"},
}


def test_reading_injected_processor_binds_the_shared_capability_key() -> None:
    calls: list[dict[str, Any]] = []

    def generate(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"title": "invalid"}

    # Reading's AI writes questions about a published passage; nothing it
    # returns can become a passage, and an unusable answer is no set at all -
    # never a built-in fallback (D-082).
    with pytest.raises(ReadingEvidenceError) as refused:
        process_article(ARTICLES["en"], support_code="vi", generate=generate)

    assert calls[0]["capability_key"] == "reading_generator"
    assert refused.value.code == "reading_processor_ungrounded"


@pytest.mark.parametrize(
    "error",
    [
        AICapabilityNotConfigured,
        AICapabilityDisabled,
        AICapabilityConfigInvalid,
        AICapabilityUnsupported,
    ],
)
def test_reading_capability_errors_do_not_use_builtin_fallback(
    error: type[AICapabilityError],
) -> None:
    def generate(**kwargs: Any) -> None:
        raise error("capability configuration failure")

    with pytest.raises(ReadingEvidenceError) as refused:
        process_article(ARTICLES["zh"], support_code="vi", generate=generate)
    assert refused.value.code == "reading_processor_unavailable"
    assert "capability configuration failure" in str(refused.value)
    assert isinstance(refused.value.__cause__, error)


@pytest.mark.parametrize("language_code", ["en", "zh"])
def test_linguistics_annotates_without_any_provider(language_code: str) -> None:
    # Segmentation and tagging are deterministic. This is the whole point of the
    # capability being local: there is nothing to configure and nothing to fail.
    configure_becoming_linguistics(SpecializedRepository(language_code))
    result = linguistic_annotations_for_essay(1)

    assert result["language_code"] == language_code
    assert result["annotations"], "the local tagger produced nothing"
    assert all(item["pos"] for item in result["annotations"])


def test_linguistics_annotations_quote_the_learner_text_exactly() -> None:
    # Offsets have to index back into the source, or the Review lens highlights
    # the wrong words.
    configure_becoming_linguistics(SpecializedRepository("en"))
    result = linguistic_annotations_for_essay(1)
    source = SpecializedRepository("en").get_linguistic_essay(1)["text"]

    for item in result["annotations"]:
        assert source[item["start"]:item["end"]] == item["fragment"]


@pytest.mark.parametrize(
    "language_code", ["en", "zh"]
)
def test_reading_uses_capability_runtime_without_legacy_selection(
    monkeypatch: pytest.MonkeyPatch, language_code: str
) -> None:
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    provider = Provider()
    install(monkeypatch, Repository(config()), provider)
    monkeypatch.setattr(platform, "active_selection", lambda: pytest.fail("legacy routing used"))
    with pytest.raises(ReadingEvidenceError):
        # The stub provider answers `{"ok": true}`: no questions, so no set.
        process_article(ARTICLES[language_code], support_code="vi", generate=platform.generate_structured)

    assert provider.calls[0]["model"] == "capability-model"


def test_linguistics_never_reaches_a_provider_in_either_runtime_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    provider = Provider()
    install(monkeypatch, Repository(config()), provider)
    monkeypatch.setattr(platform, "active_selection", lambda: pytest.fail("legacy routing used"))
    configure_becoming_linguistics(SpecializedRepository())

    linguistic_annotations_for_essay(1)

    assert provider.calls == []


@pytest.mark.parametrize("runtime_config", [None, config(enabled=False)])
def test_reading_capability_runtime_fails_closed(
    monkeypatch: pytest.MonkeyPatch, runtime_config: CapabilityConfig | None
) -> None:
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    provider = Provider()
    install(monkeypatch, Repository(runtime_config), provider)
    monkeypatch.setattr(platform, "active_selection", lambda: pytest.fail("legacy routing used"))
    with pytest.raises(ReadingEvidenceError) as refused:
        process_article(ARTICLES["en"], support_code="vi", generate=platform.generate_structured)
    assert isinstance(refused.value.__cause__, (AICapabilityNotConfigured, AICapabilityDisabled))
    assert provider.calls == []


def test_switching_to_legacy_restores_global_routing_without_deleting_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Repository(config())
    capability = Provider()
    legacy = Provider(id="legacy", name="Legacy")
    install(monkeypatch, repository, capability)
    monkeypatch.setattr(platform, "active_selection", lambda: (legacy, "legacy-model"))
    monkeypatch.setenv("AI_RUNTIME_MODE", "capability")
    request(capability_key="writing_evaluator")

    monkeypatch.setenv("AI_RUNTIME_MODE", "legacy")
    result = request(capability_key="writing_evaluator")

    assert result.model == "legacy-model"
    assert repository.get_capability_config("writing_evaluator") is not None


def test_workloads_pass_product_wide_explicit_capabilities() -> None:
    tree = ast.parse((Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8"))
    values = {
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"generate_structured", "ai_json"}
        for keyword in node.keywords
        if keyword.arg == "capability_key" and isinstance(keyword.value, ast.Constant)
    }
    assert values == {"writing_evaluator", "writing_task_generator"}
    assert not any(value.endswith(("_en", "_zh")) for value in values)

    ai_json_capabilities = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "ai_json"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert ai_json_capabilities == {
        "writing_improver", "learner_dictionary", "learner_translation"
    }
    assert "grammar_lesson_generator" not in ai_json_capabilities
    assert "writing_linguistic" not in values | ai_json_capabilities, (
        "writing_linguistic is deterministic; nothing should route it to a provider"
    )
    assert values | ai_json_capabilities | {"reading_generator"} == {
        "writing_evaluator", "reading_generator",
        "writing_task_generator", "writing_improver", "learner_dictionary",
        "learner_translation",
    }
