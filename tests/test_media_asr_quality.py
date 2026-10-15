"""ASR transcript quality (D-206, PROPOSED): one script per Chinese item, and hallucinated segments removed.

Fixtures are synthetic and shaped like what the 2026-10-14 mini trial observed; none is a real transcript."""
from __future__ import annotations

import json

from writing_coach.languages.chinese.script_conversion import convert_script, target_script
from writing_coach.languages.chinese.script_detection import SIMPLIFIED, TRADITIONAL, script_counts
from writing_coach.media_asr_filter import DATA_PATH, screen_segments
from writing_coach.media_segmentation import Cue
from writing_coach.media_transcript_pipeline import _asr_cues
from writing_coach.media_zh_cleanup import clean_asr_cues, normalise_words
from writing_coach.speech_asr import SpeechAsrResult, SpeechAsrSegment, SpeechAsrWord

S = SpeechAsrSegment


def seg(text, start, end, **signals):
    return S(text, start * 1000, end * 1000, **signals)


# -- script ------------------------------------------------------------------------------


def test_mixed_script_line_becomes_one_script():
    mixed = "这是第一次，戶口和鼓勵生育"
    out = convert_script(mixed, SIMPLIFIED)
    assert out == "这是第一次，户口和鼓励生育"
    assert script_counts(out)[1] == 0


def test_conversion_is_one_character_for_one_so_lengths_hold():
    text = "復日大學的這個故事"
    assert len(convert_script(text, SIMPLIFIED)) == len(text)


def test_traditional_target_is_honoured_and_ambiguous_characters_are_left():
    assert target_script("zh-Hant") == TRADITIONAL and target_script("zh-TW") == TRADITIONAL
    assert target_script("zh") == SIMPLIFIED and target_script("zh-CN") == SIMPLIFIED and target_script("") == SIMPLIFIED
    out = convert_script("这是第一次", TRADITIONAL)
    assert script_counts(out)[0] == 0
    assert "发" in convert_script("发", TRADITIONAL)  # 發 or 髮: not guessed


def test_cues_and_words_are_normalised_together_and_still_align():
    words = [SpeechAsrWord("戶", 0, 200), SpeechAsrWord("口", 200, 400), SpeechAsrWord("這", 2000, 2200), SpeechAsrWord("是", 2200, 2500)]
    cues = clean_asr_cues([Cue(0, 2600, "戶 口 這 是")], words, "zh")
    assert [cue.text for cue in cues] == ["户口。", "这是。"]
    assert [word.word for word in normalise_words(words, "zh")] == ["户", "口", "这", "是"]
    assert [(w.start_ms, w.end_ms) for w in normalise_words(words, "zh")] == [(w.start_ms, w.end_ms) for w in words]


def test_script_is_left_alone_for_other_languages():
    cues = [Cue(0, 1000, "戶口")]
    assert clean_asr_cues(cues, [], "en") == cues


def test_cut_without_a_pause_is_not_closed_with_a_full_stop():
    ws = [SpeechAsrWord("曾", 0, 200), SpeechAsrWord("经", 200, 400), SpeechAsrWord("撰", 450, 650), SpeechAsrWord("写", 650, 900)]
    first, second = clean_asr_cues([Cue(0, 420, "曾经"), Cue(420, 1000, "撰写")], ws, "zh")
    assert first.text == "曾经"
    assert second.text == "撰写。"


def test_cut_after_a_real_pause_is_still_closed():
    ws = [SpeechAsrWord("好", 0, 200), SpeechAsrWord("的", 2000, 2200)]
    first, _ = clean_asr_cues([Cue(0, 1000, "好"), Cue(1900, 2400, "的")], ws, "zh")
    assert first.text == "好。"


# -- hallucination filter ------------------------------------------------------------------


def texts(screen):
    return [s.text for s in screen.segments]


def test_subtitle_credit_lines_are_dropped_in_any_language():
    segments = [seg("你好吗", 0, 2), seg("中文字幕志愿者 李某", 3, 5), seg("优优独播剧场", 6, 8), seg("YoYo Television Series Exclusive", 9, 11), seg("今天天气很好", 12, 15)]
    out = screen_segments(segments, [], "zh")
    assert texts(out) == ["你好吗", "今天天气很好"] and out.filtered == 3


def test_foreign_tag_is_dropped_but_the_word_inside_a_sentence_is_kept():
    out = screen_segments([seg("We met a foreign student today.", 0, 3), seg("foreign", 4, 5), seg("[Music]", 6, 8), seg("That was a good day.", 9, 12)], [], "en")
    assert texts(out) == ["We met a foreign student today.", "That was a good day."] and out.filtered == 2


def test_stock_phrases_over_a_long_silence_are_dropped_en():
    # shape seen in the trial: sign-offs spanning 30 s of silence, one repeated three times
    segments = [seg("The machine hums in the dark room tonight.", 0, 4), seg("I'm sorry.", 5, 38), seg("I'm sorry.", 38, 40), seg("Thank you.", 41, 60), seg("The End", 60, 90)]
    out = screen_segments(segments, [], "en")
    assert texts(out) == ["The machine hums in the dark room tonight."]
    assert out.filtered == 4


def test_stock_phrases_over_a_long_silence_are_dropped_zh():
    segments = [seg("今天我们去市场买菜。", 0, 4), seg("谢谢", 5, 38), seg("谢谢观看", 40, 60)]
    out = screen_segments(segments, [], "zh")
    assert texts(out) == ["今天我们去市场买菜。"] and out.filtered == 2


def test_a_real_thank_you_inside_speech_is_kept():
    segments = [seg("Welcome to the show, everyone.", 0, 3), seg("Thank you.", 3.2, 4.2), seg("Today we talk about bread and butter.", 4.5, 8)]
    out = screen_segments(segments, [], "en")
    assert len(out.segments) == 3 and out.filtered == 0


def test_a_real_zh_thank_you_inside_speech_is_kept():
    segments = [seg("大家好。", 0, 2), seg("谢谢", 2.2, 3), seg("今天我们讲面包的故事。", 3.3, 7)]
    assert screen_segments(segments, [], "zh").filtered == 0


def test_recogniser_confidence_decides_before_any_phrase():
    segments = [
        seg("Real words about a river and a bridge.", 0, 4, no_speech_prob=0.02, avg_logprob=-0.2, compression_ratio=1.3),
        seg("Invented words over the quiet part of the film.", 5, 9, no_speech_prob=0.93, avg_logprob=-1.6, compression_ratio=1.2),
        seg("la la la la la la la la la la la la la la", 10, 14, no_speech_prob=0.01, avg_logprob=-0.4, compression_ratio=3.1),
        seg("Confident speech with a quiet moment before it.", 15, 19, no_speech_prob=0.7, avg_logprob=-0.3),
    ]
    out = screen_segments(segments, [], "en")
    assert texts(out) == ["Real words about a river and a bridge.", "Confident speech with a quiet moment before it."]
    assert out.filtered == 2


def test_sparse_long_segment_that_matches_nothing_is_flagged_not_dropped():
    out = screen_segments([seg("Hello there.", 0, 2), seg("one two", 3, 36), seg("And here is a long normal sentence now.", 37, 41)], [], "en")
    assert out.filtered == 0 and out.flagged == 1 and len(out.segments) == 3


def test_lone_words_in_the_tail_after_silence_are_dropped():
    segments = [seg("This is the last real sentence of the talk.", 0, 4), seg("The", 12, 13), seg("you", 20, 21)]
    out = screen_segments(segments, [], "en")
    assert texts(out) == ["This is the last real sentence of the talk."] and out.filtered == 2


def test_a_lone_word_right_after_speech_is_kept():
    out = screen_segments([seg("This is the last real sentence of the talk.", 0, 4), seg("Right.", 4.3, 5)], [], "en")
    assert out.filtered == 0


def test_words_inside_dropped_segments_are_removed_and_others_kept():
    words = [SpeechAsrWord("好", 500, 800), SpeechAsrWord("谢", 6000, 6300), SpeechAsrWord("谢", 6400, 6700)]
    out = screen_segments([seg("你好吗", 0, 2), seg("谢谢", 5, 38)], words, "zh")
    assert [w.word for w in out.words] == ["好"]


def test_screening_is_idempotent_and_does_not_touch_clean_input():
    segments = [seg("First clean sentence of the clip.", 0, 3), seg("Second clean sentence of the clip.", 3.5, 7)]
    first = screen_segments(segments, [], "en")
    assert list(first.segments) == segments and (first.filtered, first.flagged) == (0, 0)
    assert screen_segments(list(first.segments), [], "en").segments == first.segments


def test_phrase_list_is_a_documented_data_file_per_language():
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    assert data["basis"] and set(data) >= {"any", "en", "zh"}
    assert data["en"]["stock"] and data["zh"]["stock"]


def test_pipeline_joins_chunks_and_reports_the_count():
    results = [
        (SpeechAsrResult("t", "m", "zh", "x", (seg("今天我们去市场。", 0, 4),), ()), 0.0),
        (SpeechAsrResult("t", "m", "zh", "x", (seg("优优独播剧场", 1, 3), seg("天气很好。", 5, 8)), ()), 600.0),
    ]
    cues, _, _, screen = _asr_cues(results, "zh")
    assert [c.text for c in cues] == ["今天我们去市场。", "天气很好。"]
    assert cues[1].start_ms == 605_000
    assert screen == {"filtered": 1, "flagged": 0}
