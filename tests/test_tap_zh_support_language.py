"""A basic tap returns a meaning in the support language: catalogue, dictionary in that language, `word_translation`, and only
then the English dictionary gloss, labelled English. An English gloss is never presented as a Vietnamese meaning."""

from __future__ import annotations

import pytest

from writing_coach import media_interaction, word_detail
from writing_coach.reading_derived import DerivedCache
from writing_coach.reading_lookup import ReadingLookupService
from writing_coach.reading_translation import ReadingTranslationService
from tests.test_tap_basic_meaning import _Paid, _miss

ZH = "政府宣布了新的计划。"


def _detail(seam, text="政府", context=ZH, source="zh", target="vi", dictionary=_miss):
    service = ReadingLookupService(None, dictionary, ReadingTranslationService(_Paid(), cache=DerivedCache()), word_translation=seam)
    word_detail.configure_word_detail(lookup=service.lookup, saved_terms=None, cache=DerivedCache())
    return word_detail.word_detail(
        word_detail.WordDetailIn(text=text, context=context, source_language=source, target_language=target, depth="sheet", contextual=False)
    )


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "zh")
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    monkeypatch.setattr(word_detail, "_cache", DerivedCache())
    from writing_coach import reading_lookup

    reading_lookup.reset_seam_gate()


def test_zh_word_with_only_an_english_dictionary_asks_the_seam_for_the_support_language():
    seen = []
    out = _detail(lambda *a: seen.append(a) or "chính phủ")
    assert [(a[0], a[3], a[4]) for a in seen] == [("政府", "zh", "vi")]
    assert out["contextMeaning"] == "chính phủ" and out["meaningSource"] == "word_translation" and out["meaningLanguage"] == "vi"


def test_zh_seam_failure_falls_back_to_the_english_gloss_labelled_english():
    def boom(*_a):
        raise RuntimeError("provider down")

    for seam in (boom, lambda *a: None, None):
        out = _detail(seam)
        assert out["available"] and out["contextMeaning"], seam
        assert out["meaningSource"] == "dictionary" and out["meaningLanguage"] == "en"


def test_zh_to_english_support_needs_no_seam():
    seen = []
    out = _detail(lambda *a: seen.append(a) or "x", target="en")
    assert seen == [] and out["meaningLanguage"] == "en" and out["meaningSource"] == "dictionary"


def test_en_common_word_with_a_vietnamese_support_asks_the_seam():
    out = _detail(lambda *a: "viện trợ", text="aid", context="The aid arrived late.", source="en")
    assert out["contextMeaning"] == "viện trợ" and out["meaningLanguage"] == "vi"


def test_annotate_tags_every_word_of_a_long_chinese_paragraph():
    paragraph = "政府宣布了新的计划。" * 120  # 1200 characters, about 600 words: past the old cap of 160
    out = media_interaction.annotate_media_text(media_interaction.MediaAnnotateIn(text=paragraph, source_language="zh"))
    tagged = out["annotations"]
    assert len(tagged) > 160 and tagged[-1]["end"] >= len(paragraph.strip()) - 1


def _app_with(monkeypatch, getter):
    import app as app_module

    monkeypatch.setattr(app_module, "requests", type("R", (), {"get": staticmethod(getter), "Timeout": app_module.requests.Timeout})())
    monkeypatch.setattr(app_module, "_learning_cache", type("C", (), {"get_dictionary": lambda s, k: None, "put_dictionary": lambda *a: None})())
    monkeypatch.setattr(app_module, "is_chinese", lambda: False)
    app_module._NO_ENTRY_UNTIL.clear()
    return app_module


def test_a_dictionary_timeout_is_not_remembered_as_no_entry_for_minutes(monkeypatch):
    import time

    def slow(*_a, **_k):
        raise __import__("requests").Timeout("slow")

    app_module = _app_with(monkeypatch, slow)
    assert app_module._reading_english_dictionary("aid") == {"phonetic": ""}
    assert app_module._NO_ENTRY_UNTIL["aid"] - time.monotonic() <= app_module._UNREACHABLE_SECONDS + 1


def test_a_dictionary_404_is_remembered_as_no_entry(monkeypatch):
    import time

    class _R:
        ok, status_code = False, 404

    app_module = _app_with(monkeypatch, lambda *_a, **_k: _R())
    assert app_module._reading_english_dictionary("qwxzv") == {"phonetic": ""}
    assert app_module._NO_ENTRY_UNTIL["qwxzv"] - time.monotonic() > 60
