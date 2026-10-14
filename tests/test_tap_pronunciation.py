"""The pronunciation in the Word Quick Sheet (pinyin for Chinese, IPA for English) does not depend on which layer
answered the meaning: a Chinese word keeps its pinyin when the sentence tagger gave none, and an English word keeps
the dictionary's IPA when the meaning came from the `word_translation` seam."""

from __future__ import annotations


import pytest

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


def _fallback(monkeypatch, text, context):
    monkeypatch.setattr(reading_lookup, "_local_token_facts", _no_tagger)
    return _detail(lambda *a: "x", text=text, context=context)["pinyin"]


@pytest.mark.parametrize(
    ("word", "reading"),
    [("女人", "nǚ rén"), ("绿色", "lǜ sè"), ("東西", "dōng xī"), ("东西", None)],
)
def test_fallback_readings(monkeypatch, word, reading):
    got = _fallback(monkeypatch, word, f"这是{word}。")
    if reading is None:
        assert got and got.startswith("dōng")  # neutral tone stays as the dictionary gives it (dōng xi or dōng xī)
    else:
        assert got == reading


@pytest.mark.parametrize("char", ["了", "重", "行", "长", "还", "着", "得", "地"])
def test_single_character_polyphone_without_context_shows_no_reading(monkeypatch, char):
    assert _fallback(monkeypatch, char, f"他{char}。") is None


def test_polyphone_keeps_the_taggers_contextual_reading():
    out = _detail(lambda *a: "x", text="重", context="这个很重。")
    assert out["pinyin"] == "zhòng"


def test_erhua_word_has_a_reading(monkeypatch):
    assert _fallback(monkeypatch, "花儿", "这朵花儿很美。")


def test_dictionary_reading_from_a_later_entry_and_robust_to_bad_shapes():
    import app as app_module

    first = {"phonetic": "/a/", "phonetics": [{"text": "/a/", "audio": "//x/a.mp3"}]}
    later = {"phonetic": "", "phonetics": [{"text": "/b/", "audio": "//x/b.mp3"}]}
    assert app_module._dictionary_reading([first, later]) == ("/a/", "https://x/a.mp3")
    assert app_module._dictionary_reading([{"phonetics": [{"audio": "//x/n.mp3"}]}, later]) == ("/b/", "https://x/b.mp3")
    assert app_module._dictionary_reading([{"phonetics": None}, "junk", {"phonetics": [None, 3]}]) == ("", "")
