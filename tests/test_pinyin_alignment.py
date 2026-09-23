"""One reading under each Chinese character (D-066, DC-3).

The reading comes from the reviewed catalogue string; pypinyin only says where a
syllable ends. A line whose reading does not agree with its characters is left
unaligned, and every line the catalogue ships must align.
"""

from __future__ import annotations

import pytest

from writing_coach.listening_catalog import CATALOG
from writing_coach.listening_api import open_listening_library_lesson
from writing_coach.pinyin_alignment import align_pinyin


def cells(text: str, reading: str) -> list[tuple[str, str]]:
    aligned = align_pinyin(text, reading)
    assert aligned is not None, (text, reading)
    return [(item["char"], item["pinyin"]) for item in aligned]


def test_a_line_is_cut_into_one_syllable_per_character_keeping_the_reviewed_reading() -> None:
    assert cells("我们想要一张靠窗的桌子。", "Wǒmen xiǎng yào yì zhāng kào chuāng de zhuōzi.") == [
        ("我", "Wǒ"), ("们", "men"), ("想", "xiǎng"), ("要", "yào"), ("一", "yì"), ("张", "zhāng"),
        ("靠", "kào"), ("窗", "chuāng"), ("的", "de"), ("桌", "zhuō"), ("子", "zi"),
    ]


def test_the_reviewed_reading_wins_over_the_library_where_they_differ() -> None:
    # 谁 is "shuí" in the library and "shéi" in the reviewed line; 一 is sandhi'd to "yì".
    got = dict(cells("谁一张", "shéi yì zhāng"))
    assert got["谁"] == "shéi" and got["一"] == "yì"


def test_punctuation_and_a_speaker_label_get_no_reading_but_do_not_break_the_line() -> None:
    assert [char for char, _ in cells("金妮：他们是谁？", "Jīnní: Tāmen shì shéi?")] == list("金妮他们是谁")


def test_latin_words_are_matched_letter_for_letter_and_given_no_entry() -> None:
    assert [char for char, _ in cells("用MonoBook等版本", "yòng MonoBook děng bǎnběn")] == list("用等版本")
    assert align_pinyin("用MonoBook等版本", "yòng MonoBok děng bǎnběn") is None


@pytest.mark.parametrize(
    ("text", "reading"),
    [
        ("我们想要", "Wǒmen xiǎng"),  # a reading shorter than its characters
        ("我们", "Wǒmen yào"),  # a reading longer than its characters
        ("我们想", "Wǒmen xiǎn"),  # a letter that does not match
        ("hello", "hello"),  # nothing to read
        ("我们", ""),  # no reading at all
    ],
)
def test_a_line_that_does_not_agree_with_its_reading_is_left_unaligned(text: str, reading: str) -> None:
    assert align_pinyin(text, reading) is None


def test_every_chinese_line_the_catalogue_ships_aligns() -> None:
    """A wrong syllable in the catalogue is caught here, not by a learner."""
    checked = 0
    for lesson in CATALOG:
        if lesson.source.language != "zh":
            continue
        payload = open_listening_library_lesson(lesson.lesson_id, "en")
        aligned = payload["catalog"]["pinyin_chars_by_segment"]
        for segment in payload["transcript"]["segments"]:
            checked += 1
            assert segment["segment_id"] in aligned, (lesson.lesson_id, segment["original_text"])
            han = [ch for ch in segment["original_text"] if "一" <= ch <= "鿿"]
            assert [item["char"] for item in aligned[segment["segment_id"]]] == han
    assert checked >= 10


def test_an_english_lesson_carries_no_per_character_reading() -> None:
    payload = open_listening_library_lesson("en-daily-pen-in-my-bag", "vi")
    assert payload["catalog"]["pinyin_chars_by_segment"] == {}
