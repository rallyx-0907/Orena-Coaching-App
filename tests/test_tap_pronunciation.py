"""The pronunciation in the Word Quick Sheet (pinyin for Chinese, IPA for English) does not depend on which layer
answered the meaning: a Chinese word keeps its pinyin when the sentence tagger gave none, and an English word keeps
the dictionary's IPA when the meaning came from the `word_translation` seam."""

from __future__ import annotations


from writing_coach import reading_lookup
from tests.test_tap_zh_support_language import _detail, _isolated  # noqa: F401 - the shared fixture

ZH = "政府宣布了新的计划。"


def _no_tagger(*_args):
    return {"part_of_speech": "", "pronunciation": "", "base_form": "", "lemma": ""}


def test_zh_word_keeps_pinyin_when_the_tagger_gave_none_and_the_seam_answered(monkeypatch):
    monkeypatch.setattr(reading_lookup, "_local_token_facts", _no_tagger)
    out = _detail(lambda *a: "chính phủ")
    assert out["meaningSource"] == "word_translation"
    assert out["pinyin"] == "zhèng fǔ" and out["ipa"] is None


def test_zh_word_falls_back_to_pypinyin_when_cedict_has_no_reading(monkeypatch):
    monkeypatch.setattr(reading_lookup, "_local_token_facts", _no_tagger)
    monkeypatch.setattr(reading_lookup.chinese_lexicon, "reading", lambda _word: "")
    out = _detail(lambda *a: "chính phủ")
    assert out["pinyin"] == "zhèng fǔ"


def test_zh_tagger_reading_still_wins_over_the_fallback():
    out = _detail(lambda *a: "chính phủ")
    assert out["pinyin"] == "zhèng fǔ"


def test_en_ipa_from_the_dictionary_survives_a_meaning_from_the_seam():
    def dictionary(_word):
        return {"phonetic": "/eɪd/", "definitions": [{"part_of_speech": "noun", "definition": "help"}]}

    out = _detail(lambda *a: "viện trợ", text="aid", context="The aid arrived late.", source="en", dictionary=dictionary)
    assert out["contextMeaning"] == "viện trợ"
    assert out["ipa"] == "/eɪd/" and out["pinyin"] is None
