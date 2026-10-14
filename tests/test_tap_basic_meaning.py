"""A basic tap always answers from deterministic layers, in order, and one layer failing never blanks the sheet.

Catalogue -> dictionary -> free local translation. The reading translation engine may be the paid platform AI (the
default); the tap must then still reach the free local translator rather than ending at "not prepared"."""

from __future__ import annotations

import pytest

from writing_coach import media_interaction, word_detail
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService


class _Engine:
    model_version = "x-1"

    def __init__(self, engine_id: str, meanings: dict[str, str] | None = None, fail: bool = False) -> None:
        self.engine_id = engine_id
        self.meanings = meanings or {}
        self.fail = fail
        self.calls = 0

    def translate_batch(self, source_language, target_language, segments):
        self.calls += 1
        if self.fail:
            from writing_coach.media_translation import TranslationProviderError

            raise TranslationProviderError("down")
        return {s.segment_id: self.meanings.get(s.original_text, "") for s in segments}


class _Catalogue:
    def __init__(self, entries=None, raises: Exception | None = None) -> None:
        self.entries = entries or {}
        self.raises = raises

    def find_entry(self, language_code, normalized_term):
        if self.raises:
            raise self.raises
        return self.entries.get((language_code, normalized_term))


def _miss(_word):
    return {"phonetic": ""}


def _boom(_word):
    raise RuntimeError("dictionary down")


def _service(primary, local, *, catalogue=None, dictionary=_miss):
    cache = DerivedCache()
    return ReadingLookupService(
        catalogue,
        dictionary,
        ReadingTranslationService(primary, cache=cache),
        local_translation_service=ReadingTranslationService(local, cache=cache) if local is not None else None,
    )


@pytest.fixture
def no_ai(monkeypatch):
    calls: list[str] = []

    def spy(capability_key, **_k):
        calls.append(capability_key)
        raise AssertionError("a basic tap must not reach the AI provider")

    monkeypatch.setattr(media_interaction, "_run_structured", spy)
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    monkeypatch.setattr(word_detail, "_cache", DerivedCache())
    return calls


def _detail(service, text, context, source):
    word_detail.configure_word_detail(lookup=service.lookup, saved_terms=None, cache=DerivedCache())
    return word_detail.word_detail(
        word_detail.WordDetailIn(text=text, context=context, source_language=source, target_language="vi", depth="sheet", contextual=False)
    )


EN_SENTENCE = "A poetry book promotes Chabacano, Asia's only Spanish-based creole language."
ZH_SENTENCE = "这本诗集推广语言。"


def test_en_to_vi_reaches_the_local_translator_when_the_reading_engine_is_the_paid_ai(no_ai):
    ai = _Engine("ai", {"poetry": "AI MUST NOT BE USED"})
    local = _Engine("local_marian", {"poetry": "thơ"})
    out = _detail(_service(ai, local), "poetry", EN_SENTENCE, "en")
    assert out["contextMeaning"] == "thơ" and out["meaningSource"] == "dictionary" and out["meaningLanguage"] == "vi"
    assert out["available"] is True and out["partOfSpeech"] == "noun"
    assert out["contextSentence"] == EN_SENTENCE
    assert ai.calls == 0 and no_ai == []


def test_zh_to_vi_reaches_the_local_translator_and_keeps_the_cedict_original(no_ai):
    ai = _Engine("ai")
    local = _Engine("local_marian", {"语言": "ngôn ngữ"})
    out = _detail(_service(ai, local), "语言", ZH_SENTENCE, "zh")
    assert out["contextMeaning"] == "ngôn ngữ" and out["meaningLanguage"] == "vi"
    assert out["originalDefinition"] and out["originalDefinition"]["language"] == "en"
    assert ai.calls == 0 and no_ai == []


def test_a_failing_dictionary_does_not_blank_the_sheet_when_translation_can_answer(no_ai):
    out = _detail(_service(_Engine("ai"), _Engine("local_marian", {"poetry": "thơ"}), dictionary=_boom), "poetry", EN_SENTENCE, "en")
    assert out["contextMeaning"] == "thơ" and out["available"] is True


def test_a_failing_catalogue_does_not_stop_the_dictionary_or_translation(no_ai):
    catalogue = _Catalogue(raises=RuntimeError("catalogue down"))
    out = _detail(_service(_Engine("ai"), _Engine("local_marian", {"poetry": "thơ"}), catalogue=catalogue), "poetry", EN_SENTENCE, "en")
    assert out["contextMeaning"] == "thơ"
    dictionary = lambda w: {"definitions": [{"part_of_speech": "noun", "definition": "verse"}], "phonetic": "/p/"}  # noqa: E731
    out = _detail(_service(_Engine("ai"), None, catalogue=catalogue, dictionary=dictionary), "poetry", EN_SENTENCE, "en")
    assert out["contextMeaning"] == "verse" and out["meaningSource"] == "dictionary"


def test_a_down_local_translator_leaves_the_dictionary_meaning(no_ai):
    dictionary = lambda w: {"definitions": [{"part_of_speech": "noun", "definition": "verse"}], "phonetic": ""}  # noqa: E731
    out = _detail(_service(_Engine("ai"), _Engine("local_marian", fail=True), dictionary=dictionary), "poetry", EN_SENTENCE, "en")
    assert out["contextMeaning"] == "verse" and out["available"] is True


def test_the_catalogue_meaning_still_wins_and_translation_is_not_asked(no_ai):
    catalogue = _Catalogue({("en", "poetry"): {"term": "poetry", "short_meanings": [{"language": "vi", "text": "thi ca"}]}})
    local = _Engine("local_marian", {"poetry": "thơ"})
    out = _detail(_service(_Engine("ai"), local, catalogue=catalogue), "poetry", EN_SENTENCE, "en")
    assert out["contextMeaning"] == "thi ca" and local.calls == 0


def test_a_paid_engine_is_never_the_local_fallback(no_ai):
    ai = _Engine("ai", {"poetry": "x"})
    paid_as_local = _Engine("groq", {"poetry": "y"})
    out = _detail(_service(ai, paid_as_local), "poetry", EN_SENTENCE, "en")
    assert out["available"] is False and ai.calls == 0 and paid_as_local.calls == 0


def test_every_layer_missing_is_the_only_unavailable_case(no_ai):
    out = _detail(_service(_Engine("ai"), _Engine("local_marian", {})), "poetry", EN_SENTENCE, "en")
    assert out["available"] is False and out["meaningSource"] == "none"
