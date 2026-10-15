"""Chinese speech-recognition cleanup: no spaces between Hanzi, sentence marks restored deterministically, leading
silence trimmed to the first word. Pure functions; English is never touched; applying it twice changes nothing."""
from __future__ import annotations

import pytest

from writing_coach.languages.chinese.script_detection import script_counts
from writing_coach.media_segmentation import Cue, segment_lines
from writing_coach.media_zh_cleanup import clean_asr_cues
from writing_coach.speech_asr import SpeechAsrWord


def words(*items: tuple[str, int, int]) -> list[SpeechAsrWord]:
    return [SpeechAsrWord(text, start, end) for text, start, end in items]


def spaced(text: str) -> str:
    return " ".join(text)


def one(text: str, language: str = "zh") -> str:
    [cue] = clean_asr_cues([Cue(0, 3000, text)], [], language)
    return cue.text


def test_spaces_between_hanzi_are_removed_and_latin_keeps_its_spaces():
    [cue] = clean_asr_cues([Cue(0, 4000, "我 喜欢 iPhone 15 手机")], [], "zh")
    assert cue.text.startswith("我喜欢 iPhone 15 手机")
    assert " 手机" in cue.text and "我 " not in cue.text


def test_cue_end_gets_a_full_width_mark_and_questions_get_a_question_mark():
    first, second = clean_asr_cues([Cue(0, 2000, "你 喜欢 熊猫 吗"), Cue(2500, 4500, "他 是 神龙 大侠")], [], "zh")
    assert first.text == "你喜欢熊猫吗？"
    assert second.text == "他是神龙大侠。"


@pytest.mark.parametrize("text,expected", [
    ("你喜歡熊貓嗎", "你喜歡熊貓嗎？"),
    ("你是誰", "你是誰？"),
    ("這是甚麼", "這是甚麼？"),
    ("你怎麼了", "你怎麼了？"),
    ("為什麼不去", "為什麼不去？"),
    ("你有幾個朋友", "你有幾個朋友？"),
    ("你住在哪裡", "你住在哪裡？"),
    ("你喜欢熊猫吗", "你喜欢熊猫吗？"),
    ("你呢", "你呢？"),
    ("这是什么", "这是什么？"),
])
def test_questions_in_both_scripts_get_a_question_mark(text, expected):
    # An item is written in one script: Traditional text keeps its forms only for a Traditional item (D-208).
    language = "zh-Hant" if script_counts(text)[1] else "zh"
    assert one(spaced(text), language) == expected


@pytest.mark.parametrize("text", [
    "我不知道他在说什么",
    "我怎么也不明白",
    "谁都知道",
    "你说什么，我听不见",
    "他在吃饭呢",
    "你别说嘛",
    "我不知道他是誰",
])
def test_statements_that_hold_a_question_word_stay_statements(text):
    assert one(spaced(text), "zh-Hant" if script_counts(text)[1] else "zh") == text + "。"


def test_pauses_between_words_become_commas_and_sentence_marks():
    ws = words(("我", 0, 200), ("来", 220, 400), ("了", 420, 600), ("你", 1300, 1500), ("呢", 1520, 1800), ("好", 3100, 3300), ("的", 3320, 3500))
    [first, second] = clean_asr_cues([Cue(0, 3600, "我 来 了 你 呢 好 的")], ws, "zh")
    assert first.text == "我来了，你呢？"
    assert (first.start_ms, first.end_ms) == (0, 1800)
    assert second.text == "好的。"
    assert (second.start_ms, second.end_ms) == (3100, 3600)


def test_ordinary_jitter_is_not_a_comma_and_no_mark_separates_a_particle():
    ws = words(("我", 0, 200), ("来", 550, 700), ("你", 900, 1100), ("呢", 1700, 1900))
    [cue] = clean_asr_cues([Cue(0, 2000, "我 来 你 呢")], ws, "zh")
    assert cue.text == "我来你呢？"  # 350 ms is not a pause; the 600 ms one before 呢 is not cut off from it


def test_a_clear_pause_between_clauses_is_a_comma():
    ws = words(("我", 0, 200), ("来", 220, 400), ("你", 1000, 1200), ("好", 1220, 1400))
    [cue] = clean_asr_cues([Cue(0, 1500, "我 来 你 好")], ws, "zh")
    assert cue.text == "我来，你好。"


def test_leading_silence_is_trimmed_to_the_first_word():
    ws = words(("神", 11000, 11300), ("龙", 11300, 11600), ("来", 11700, 12000))
    [cue] = clean_asr_cues([Cue(0, 12100, "神 龙 来")], ws, "zh")
    assert (cue.start_ms, cue.end_ms, cue.text) == (11000, 12100, "神龙来。")


def test_previous_cues_last_word_is_not_this_cues_first_word():
    ws = words(("好", 900, 1980), ("神", 5000, 5300), ("龙", 5300, 5600))
    first, second = clean_asr_cues([Cue(0, 2000, "好"), Cue(2000, 6000, "神 龙")], ws, "zh")
    assert second.start_ms == 5000 and second.text == "神龙。"


def test_idempotent():
    ws = words(("我", 500, 700), ("来", 720, 900), ("去", 1600, 1800), ("好", 3200, 3400))
    cues = [Cue(0, 3500, "我 来 去 好")]
    once = clean_asr_cues(cues, ws, "zh")
    twice = clean_asr_cues(once, ws, "zh")
    assert once == twice
    assert [cue.text for cue in once] == ["我来，去。", "好。"]
    assert once[0].start_ms == 500


def test_half_width_marks_next_to_hanzi_become_full_width():
    assert one("你好, 你是谁?") == "你好，你是谁？"


def test_english_and_unknown_languages_are_untouched():
    cues = [Cue(0, 2000, "I  like  pandas"), Cue(2000, 3000, "ok")]
    assert clean_asr_cues(cues, [], "en") == cues
    assert clean_asr_cues(cues, [], "") == cues


def test_cues_without_hanzi_get_no_mark():
    cues = clean_asr_cues([Cue(0, 1000, "OK"), Cue(1000, 2000, "[音乐]")], [], "zh")
    assert cues[0].text == "OK"
    assert cues[1].text == "[音乐]。"  # it holds Hanzi


def test_words_that_do_not_match_the_text_are_ignored_for_punctuation():
    ws = words(("完全", 0, 300), ("不同", 1800, 2000))
    [cue] = clean_asr_cues([Cue(0, 2100, "我 来 了")], ws, "zh")
    assert cue.text == "我来了。"


def test_sentence_break_is_cut_at_the_real_pause_and_keeps_every_word():
    ws = words(("我", 0, 200), ("来", 220, 400), ("你", 2000, 2200), ("好", 2220, 2500))
    cues = clean_asr_cues([Cue(0, 2600, "我 来 你 好")], ws, "zh")
    assert [(c.start_ms, c.end_ms, c.text) for c in cues] == [(0, 400, "我来。"), (2000, 2600, "你好。")]
    lines = segment_lines(cues, "zh")
    assert [(line.start_ms, line.end_ms, line.text) for line in lines] == [(0, 400, "我来。"), (2000, 2600, "你好。")]
    for word in ws:
        assert any(word.start_ms >= line.start_ms and word.end_ms <= line.end_ms for line in lines), word
