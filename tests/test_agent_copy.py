"""The agent's own learner copy: layered (D-080), and silent about providers."""

from __future__ import annotations

import pytest

from writing_coach.agent import learner_copy
from writing_coach.agent.errors import ERROR_KINDS, AgentError, ProviderUnavailable, VoiceUnavailable
from writing_coach.agent.events import error_event
from writing_coach.ai.providers import provider_definitions


def test_every_key_declares_a_layer_and_has_every_pack():
    assert learner_copy.CATALOG
    for key, entry in learner_copy.CATALOG.items():
        assert entry.layer in (learner_copy.CopyLayer.INTERFACE, learner_copy.CopyLayer.SUPPORT), key
        assert set(entry.texts) == set(learner_copy.PACK_LANGUAGES), key
        assert all(text.strip() for text in entry.texts.values()), key


def test_there_is_no_target_layer_copy():
    assert {layer.value for layer in learner_copy.CopyLayer} == {"interface", "support"}


def test_support_copy_follows_the_support_language_not_the_interface():
    language, text = learner_copy.text("error.provider_unavailable", interface="en", support="vi")
    assert (language, text) == ("vi", "Orena đang bận, thử lại sau nhé.")
    assert learner_copy.text("error.provider_unavailable", interface="vi", support="zh-CN")[0] == "zh-CN"


def test_a_support_language_without_a_pack_reads_english_never_the_interface():
    language, _ = learner_copy.text("error.internal", interface="vi", support="ja")
    assert language == "en"


def test_a_new_entry_without_every_pack_is_refused():
    with pytest.raises(ValueError):
        learner_copy._entry(learner_copy.CopyLayer.SUPPORT, {"en": "Hi", "vi": "Chào"})


def test_error_kinds_have_support_copy_and_contract_fallbacks():
    for kind in ERROR_KINDS.values():
        assert learner_copy.CATALOG[kind.copy_key].layer is learner_copy.CopyLayer.SUPPORT
    assert ERROR_KINDS["provider_unavailable"].fallback == "retry"
    assert ERROR_KINDS["voice_unavailable"].fallback == "text_only"
    assert {kind.fallback for kind in ERROR_KINDS.values()} <= {"retry", "text_only"}


def test_exceptions_name_their_error_class():
    assert ProviderUnavailable.error_class in ERROR_KINDS
    assert VoiceUnavailable.error_class in ERROR_KINDS
    assert AgentError.error_class in ERROR_KINDS


def _provider_words() -> set[str]:
    words = {"gemini", "openai", "gpt", "groq", "deepseek", "ollama", "azure", "anthropic", "claude", "google", "kokoro"}
    for definition in provider_definitions():
        words.add(definition.id.casefold())
        words.update(part.casefold() for part in definition.name.split() if part.casefold() != "api")
    return words


@pytest.mark.parametrize("error_class", sorted(ERROR_KINDS))
@pytest.mark.parametrize("support", ["en", "vi", "zh-CN", "ja"])
def test_error_messages_never_name_a_provider(error_class, support):
    message = error_event(error_class, interface="en", support=support).message.casefold()
    assert not any(word in message for word in _provider_words()), message


def test_every_copy_text_is_silent_about_providers():
    words = _provider_words()
    for key, entry in learner_copy.CATALOG.items():
        for text in entry.texts.values():
            assert not any(word in text.casefold() for word in words), key



def test_every_surface_is_named_from_the_uis_published_file_and_nowhere_else():
    # Contract v5 §6.2: the UI publishes names (and purposes) in surfaces.json; the server keeps no copy.
    from writing_coach.agent import surfaces
    from writing_coach.agent.contract import SURFACES

    assert not [key for key in learner_copy.CATALOG if key.startswith("surface.")]
    for surface in SURFACES:
        for language in ("en", "vi", "zh-CN"):
            assert surfaces.name(surface, language), (surface, language)
    assert surfaces.name("vocabulary.my_language", "vi") == surfaces.published()["vocabulary.my_language"]["name"]["vi"]
    assert surfaces.name("no.such.place", "vi") is None


def test_a_purpose_is_used_only_when_the_ui_wrote_one(monkeypatch):
    from types import MappingProxyType

    from writing_coach.agent import surfaces

    table = {"home": {"name": {"en": "Today", "vi": "Hôm nay", "zh-CN": "今天"},
                      "purpose": {"en": "Start here.", "vi": "Bắt đầu ở đây.", "zh-CN": "从这里开始。"}},
             "library": {"name": {"en": "Discover", "vi": "Khám phá", "zh-CN": "发现"}}}  # fmt: skip
    monkeypatch.setattr(surfaces, "published", lambda: MappingProxyType(table))
    assert surfaces.purpose("home", "vi") == "Bắt đầu ở đây."
    assert surfaces.purpose("library", "vi") is None  # no purpose of the server's own
