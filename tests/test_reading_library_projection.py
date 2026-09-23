"""The duration a learner is told, derived and never stored.

The Book detail frames draw a time on every chapter and a remainder on the
book. `word_count` was already stored; the pace was already chosen. This is
the projection that joins them - and the tests that keep it a projection.
"""

import pytest

from writing_coach import reading_processing
from writing_coach.reading_library_api import _with_reading_time, reading_seconds


def test_the_pace_is_the_products_own_and_is_not_redefined():
    """If someone forks the constant, a learner reading a book and a learner
    reading an article are told different things about the same text."""

    assert reading_seconds(reading_processing.EN_WORDS_PER_MINUTE, "en") == 60
    assert reading_seconds(reading_processing.ZH_CHARS_PER_MINUTE, "zh") == 60


def test_chinese_is_counted_in_characters_and_english_in_words():
    same_count = 900
    assert reading_seconds(same_count, "en") > reading_seconds(same_count, "zh")


def test_a_language_the_pace_does_not_know_still_gets_a_duration():
    """A rough number is more use than a blank where the frame draws one."""

    assert reading_seconds(900, "no") == reading_seconds(900, "en")
    assert reading_seconds(900, "") == reading_seconds(900, "en")


@pytest.mark.parametrize("count", [0, None, "", -5, "not a number"])
def test_nothing_to_count_is_no_duration_rather_than_zero_minutes(count):
    assert reading_seconds(count, "en") == 0


def test_the_projection_reaches_every_chapter():
    book = {
        "id": "b1",
        "title": "Kafka",
        "learning_language": "en",
        "word_count": 3600,
        "chapters": [
            {"id": "c1", "position": 1, "title": "One", "word_count": 1800},
            {"id": "c2", "position": 2, "title": "Two", "word_count": 0},
        ],
    }
    projected = _with_reading_time(book)
    assert projected["reading_time_seconds"] == reading_seconds(3600, "en")
    assert [chapter["reading_time_seconds"] for chapter in projected["chapters"]] == [
        reading_seconds(1800, "en"),
        0,
    ]
    # Everything the repository gave is still there, untouched.
    assert projected["chapters"][0]["title"] == "One"
    assert projected["title"] == "Kafka"


def test_the_projection_does_not_mutate_what_it_was_given():
    """It is a read model. The repository's dict is the repository's."""

    book = {
        "learning_language": "en",
        "word_count": 900,
        "chapters": [{"id": "c1", "word_count": 900}],
    }
    _with_reading_time(book)
    assert "reading_time_seconds" not in book
    assert "reading_time_seconds" not in book["chapters"][0]


def test_a_book_with_no_chapters_is_projected_without_inventing_any():
    assert _with_reading_time({"learning_language": "en", "word_count": 0}).get("chapters") is None
    assert _with_reading_time({"learning_language": "en", "chapters": []})["chapters"] == []


def test_nothing_about_the_import_path_is_involved():
    """The admin EPUB import writes assets then a row; this touches neither."""

    source = (
        __import__("pathlib")
        .Path(__file__)
        .resolve()
        .parents[1]
        .joinpath("writing_coach/reading_library_api.py")
        .read_text(encoding="utf-8")
    )
    projection = source[source.index("def reading_seconds") : source.index('@router.get("/books")')]
    for forbidden in ("asset_store", "create_book", "UploadFile", "_admin_guard"):
        assert forbidden not in projection, f"the projection reaches into {forbidden}"
