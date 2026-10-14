"""A basic tap answers from deterministic layers in order (catalogue, dictionary, free translation), never from AI, and
one failing layer never blanks the sheet. `word_translation` is a seam with no implementation yet."""

from __future__ import annotations

import pytest

from writing_coach import media_interaction, word_detail
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService


class _Paid:
    """The reading engine is the paid platform AI by default: a basic tap must never use it."""

    engine_id = "ai"
    model_version = "x"
    uses_ai = True
    uses_paid_provider = True
    calls = 0

    def translate_batch(self, *_a, **_k):
        _Paid.calls += 1
        raise AssertionError("the paid reading engine must not be used by a tap")


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


def _definition(text):
    return lambda _w: {"definitions": [{"part_of_speech": "noun", "definition": text}], "phonetic": ""}


def _service(*, catalogue=None, dictionary=_miss, seam=None):
    return ReadingLookupService(catalogue, dictionary, ReadingTranslationService(_Paid(), cache=DerivedCache()), word_translation=seam)


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
    _Paid.calls = 0
    return calls


def _detail(service, text, context, source):
    word_detail.configure_word_detail(lookup=service.lookup, saved_terms=None, cache=DerivedCache())
    return word_detail.word_detail(
        word_detail.WordDetailIn(text=text, context=context, source_language=source, target_language="vi", depth="sheet", contextual=False)
    )


EN = "A poetry book promotes Chabacano, Asia's only Spanish-based creole language."
ZH = "这本诗集推广语言。"


def test_en_dictionary_sense_answers_when_the_catalogue_misses(no_ai):
    out = _detail(_service(dictionary=_definition("verse; poems")), "poetry", EN, "en")
    assert out["contextMeaning"] == "verse; poems" and out["meaningSource"] == "dictionary" and out["available"]
    assert out["partOfSpeech"] == "noun" and out["contextSentence"] == EN
    assert _Paid.calls == 0 and no_ai == []


def test_zh_cedict_sense_answers_for_a_vietnamese_sheet_without_ai(no_ai):
    out = _detail(_service(), "语言", ZH, "zh")
    assert out["available"] and out["meaningSource"] == "dictionary" and out["contextMeaning"]
    assert out["originalDefinition"] is None or out["originalDefinition"]["language"] == "en"
    assert _Paid.calls == 0 and no_ai == []


def test_catalogue_wins_and_the_seam_is_not_asked(no_ai):
    asked = []
    catalogue = _Catalogue({("en", "poetry"): {"term": "poetry", "short_meanings": [{"language": "vi", "text": "thi ca"}]}})
    out = _detail(_service(catalogue=catalogue, seam=lambda *a: asked.append(a)), "poetry", EN, "en")
    assert out["contextMeaning"] == "thi ca" and asked == []


def test_a_failing_dictionary_or_catalogue_does_not_blank_the_sheet(no_ai):
    seam = lambda term, ctx, defs, src, tgt: "thơ"  # noqa: E731
    assert _detail(_service(dictionary=_boom, seam=seam), "poetry", EN, "en")["contextMeaning"] == "thơ"
    broken = _Catalogue(raises=RuntimeError("catalogue down"))
    out = _detail(_service(catalogue=broken, dictionary=_definition("verse")), "poetry", EN, "en")
    assert out["contextMeaning"] == "verse" and out["partOfSpeech"] == "noun"


def test_the_seam_receives_the_word_sentence_senses_and_languages(no_ai):
    seen = []
    out = _detail(_service(dictionary=_definition("verse"), seam=lambda *a: seen.append(a) or "thơ"), "poetry", EN, "en")
    assert seen == [("poetry", EN, ["verse"], "en", "vi")] and out["contextMeaning"] == "thơ"


def test_the_seam_answer_is_a_dictionary_sense_in_the_support_language(no_ai):
    out = _detail(_service(seam=lambda *a: "thơ"), "poetry", EN, "en")
    assert out["contextMeaning"] == "thơ" and out["meaningSource"] == "word_translation" and out["meaningLanguage"] == "vi"


def test_a_slow_seam_never_holds_the_tap_and_is_a_miss(no_ai, monkeypatch):
    import time

    from writing_coach import reading_lookup

    monkeypatch.setattr(reading_lookup, "SEAM_MIN_WAIT_SECONDS", 0.25)  # the floor has its own test

    service = ReadingLookupService(
        None, _definition("verse"), ReadingTranslationService(_Paid(), cache=DerivedCache()),
        budget_seconds=0.3, word_translation=lambda *a: time.sleep(2) or "thơ",
    )
    started = time.perf_counter()
    out = _detail(service, "poetry", EN, "en")
    assert time.perf_counter() - started < 1.2
    assert out["contextMeaning"] == "verse" and out["available"]


def test_the_machine_translation_guard_refuses_an_ai_engine():
    from writing_coach.reading_lookup import _safe_machine_translation

    assert _safe_machine_translation(ReadingTranslationService(_Paid(), cache=DerivedCache()), "en", "vi", "poetry") is None
    assert _Paid.calls == 0


def test_a_failing_seam_is_a_miss_and_the_dictionary_sense_stands(no_ai):
    def bad(*_a):
        raise RuntimeError("down")

    out = _detail(_service(dictionary=_definition("verse"), seam=bad), "poetry", EN, "en")
    assert out["contextMeaning"] == "verse" and out["available"]


def test_unavailable_only_after_every_layer_missed(no_ai):
    out = _detail(_service(), "poetry", EN, "en")
    assert out["available"] is False and out["meaningSource"] == "none"
    assert _Paid.calls == 0 and no_ai == []
