"""Signal-gated ASR filter rules and run-start clearing of the screen counts (D-208, PROPOSED; review of PR #218)."""
from __future__ import annotations

from writing_coach.media_asr_filter import screen_segments
from writing_coach.speech_asr import SpeechAsrSegment as S

CONFIDENT = {"no_speech_prob": 0.02, "avg_logprob": -0.2, "compression_ratio": 1.3}
DOUBTFUL = {"no_speech_prob": 0.45, "avg_logprob": -0.4, "compression_ratio": 1.3}


def seg(text, start, end, **signals):
    return S(text, int(start * 1000), int(end * 1000), **signals)


def test_confident_thank_you_after_long_silence_is_kept_and_flagged():
    out = screen_segments([seg("Welcome to the show, everyone.", 0, 3, **CONFIDENT), seg("Thank you.", 20, 21, **CONFIDENT)], [], "en")
    assert len(out.segments) == 2 and out.filtered == 0 and out.flagged == 1


def test_doubted_thank_you_after_long_silence_is_dropped():
    out = screen_segments([seg("Welcome to the show, everyone.", 0, 3, **CONFIDENT), seg("Thank you.", 20, 21, **DOUBTFUL)], [], "en")
    assert out.filtered == 1


def test_high_compression_ratio_counts_as_doubt():
    loop = {"no_speech_prob": 0.02, "avg_logprob": -0.2, "compression_ratio": 2.1}
    out = screen_segments([seg("Welcome to the show, everyone.", 0, 3, **CONFIDENT), seg("Thank you.", 20, 21, **loop)], [], "en")
    assert out.filtered == 1


def test_without_any_signal_the_silence_rule_still_applies():
    out = screen_segments([seg("Welcome to the show, everyone.", 0, 3), seg("Thank you.", 20, 21)], [], "en")
    assert out.filtered == 1


def test_confident_repeated_bye_is_kept_and_flagged():
    out = screen_segments([seg("It was lovely to see you again.", 0, 3, **CONFIDENT), seg("Bye.", 3.5, 4, **CONFIDENT), seg("Bye.", 4.2, 4.6, **CONFIDENT)], [], "en")
    assert out.filtered == 0 and out.flagged == 2


def test_confident_zh_closing_after_a_pause_is_kept_and_flagged():
    out = screen_segments([seg("那我们明天再谈这件事。", 0, 4, **CONFIDENT), seg("好的", 9, 10, **CONFIDENT)], [], "zh")
    assert len(out.segments) == 2 and out.filtered == 0 and out.flagged == 1


def test_doubted_lone_tail_word_is_dropped_with_signals():
    out = screen_segments([seg("This is the last real sentence of the talk.", 0, 4, **CONFIDENT), seg("you", 12, 13, **DOUBTFUL)], [], "en")
    assert out.filtered == 1


def test_credit_lines_and_tags_drop_even_with_confident_signals():
    out = screen_segments([seg("字幕由志愿者提供", 0, 3, **CONFIDENT), seg("[Music]", 4, 6, **CONFIDENT)], [], "zh")
    assert out.filtered == 2
