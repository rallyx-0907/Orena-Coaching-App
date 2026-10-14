"""Chinese speech-recognition cleanup: no spaces between Hanzi, sentence marks restored deterministically, leading
silence trimmed to the first word. Pure functions; English is never touched; applying it twice changes nothing."""
from __future__ import annotations

from writing_coach.media_segmentation import Cue, segment_lines
from writing_coach.media_zh_cleanup import clean_asr_cues
from writing_coach.speech_asr import SpeechAsrWord


def words(*items: tuple[str, int, int]) -> list[SpeechAsrWord]:
    return [SpeechAsrWord(text, start, end) for text, start, end in items]


def test_spaces_between_hanzi_are_removed_and_latin_keeps_its_spaces():
    cues = [Cue(0, 4000, "我 喜欢 iPhone 15 手机")]
    [cue] = clean_asr_cues(cues, [], "zh")
    assert cue.text.startswith("我喜欢 iPhone 15 手机")
    assert " 手机" in cue.text and "我 " not in cue.text


def test_cue_end_gets_a_full_width_mark_and_questions_get_a_question_mark():
    cues = [Cue(0, 2000, "你 喜欢 熊猫 吗"), Cue(2500, 4500, "他 是 神龙 大侠")]
    first, second = clean_asr_cues(cues, [], "zh")
    assert first.text == "你喜欢熊猫吗？"
    assert second.text == "他是神龙大侠。"


def test_pauses_between_words_become_commas_and_sentence_marks():
    ws = words(("我", 0, 200), ("来", 220, 400), ("了", 420, 600), ("你", 1000, 1200), ("呢", 1220, 1500), ("好", 2800, 3000), ("的", 3020, 3200))
    cues = [Cue(0, 3300, "我 来 了 你 呢 好 的")]
    [cue] = clean_asr_cues(cues, ws, "zh")
    assert cue.text == "我来了，你呢？好的。"


def test_leading_silence_is_trimmed_to_the_first_word():
    ws = words(("神", 11000, 11300), ("龙", 11300, 11600), ("来", 11700, 12000))
    [cue] = clean_asr_cues([Cue(0, 12100, "神 龙 来")], ws, "zh")
    assert cue.start_ms == 11000
    assert cue.end_ms == 12100
    assert cue.text == "神龙来。"


def test_idempotent():
    ws = words(("我", 500, 700), ("来", 720, 900), ("了", 1500, 1700))
    once = clean_asr_cues([Cue(0, 1800, "我 来 了")], ws, "zh")
    twice = clean_asr_cues(once, ws, "zh")
    assert once == twice
    assert once[0].text == "我来，了。"
    assert once[0].start_ms == 500


def test_half_width_marks_next_to_hanzi_become_full_width():
    [cue] = clean_asr_cues([Cue(0, 2000, "你好, 你是谁?")], [], "zh")
    assert cue.text == "你好，你是谁？"


def test_english_and_unknown_languages_are_untouched():
    cues = [Cue(0, 2000, "I  like  pandas"), Cue(2000, 3000, "ok")]
    assert clean_asr_cues(cues, [], "en") == cues
    assert clean_asr_cues(cues, [], "") == cues


def test_words_that_do_not_match_the_text_are_ignored_for_punctuation():
    ws = words(("完全", 0, 300), ("不同", 1800, 2000))
    [cue] = clean_asr_cues([Cue(0, 2100, "我 来 了")], ws, "zh")
    assert cue.text == "我来了。"


def test_marks_inserted_mid_cue_split_into_sentence_lines():
    ws = words(("我", 0, 200), ("来", 220, 400), ("你", 2000, 2200), ("好", 2220, 2500))
    cues = clean_asr_cues([Cue(0, 2600, "我 来 你 好")], ws, "zh")
    lines = segment_lines(cues, "zh")
    assert [line.text for line in lines] == ["我来。你好。"] or [line.text for line in lines] == ["我来。", "你好。"]
    assert all(" " not in line.text for line in lines)
