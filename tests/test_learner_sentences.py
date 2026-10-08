"""CÂU CỦA BẠN: the learner's own sentences, pulled out of their own writing.

The database narrows the search to pieces of writing that contain the word;
this is the step that turns a paragraph into the sentence the deep card draws,
and it is the part most likely to be got wrong quietly.
"""

from writing_coach.persistence.specialized_repository import _like, _sentences_from


def rows(*texts):
    return [{"text": text, "created_at": "2026-09-20T10:00:00Z", "checked": True} for text in texts]


def test_only_the_sentences_that_use_the_word_come_back():
    found = _sentences_from(
        rows("I walked to the harbour. The sky was grey. We left the harbour at dawn."),
        "harbour",
        4,
    )
    assert [item["text"] for item in found] == [
        "I walked to the harbour.",
        "We left the harbour at dawn.",
    ]


def test_a_chinese_full_stop_ends_a_sentence_too():
    found = _sentences_from(rows("我想学中文。今天天气很好。我很想家。"), "想", 4)
    assert [item["text"] for item in found] == ["我想学中文。", "我很想家。"]


def test_the_same_sentence_written_twice_is_shown_once():
    found = _sentences_from(rows("I like the harbour.", "I like the harbour."), "harbour", 4)
    assert len(found) == 1


def test_the_limit_is_the_limit():
    found = _sentences_from(
        rows("a harbour. b harbour. c harbour. d harbour. e harbour."), "harbour", 2
    )
    assert len(found) == 2


def test_a_word_never_written_has_no_section():
    assert _sentences_from(rows("Nothing to do with it."), "harbour", 4) == []


def test_matching_ignores_case_but_keeps_the_learners_own_writing():
    found = _sentences_from(rows("Harbour lights were on."), "harbour", 4)
    assert found[0]["text"] == "Harbour lights were on."


def test_the_written_date_and_whether_it_was_checked_travel_with_the_sentence():
    found = _sentences_from(
        [{"text": "The harbour is quiet.", "created_at": "2026-03-12T08:00:00Z", "checked": False}],
        "harbour",
        4,
    )
    assert found[0]["written_on"] == "2026-03-12T08:00:00Z"
    assert found[0]["checked"] is False


def test_a_like_pattern_cannot_be_smuggled_in_through_the_word():
    # A learner searching for "100%" must not match every essay.
    assert _like("100%") == "100\\%"
    assert _like("a_b") == "a\\_b"
    assert _like("back\\slash") == "back\\\\slash"
