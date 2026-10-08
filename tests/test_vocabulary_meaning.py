"""Server-side saved-word meaning for the learner's support language (D-124)."""

from __future__ import annotations

from writing_coach import collection_query, vocabulary_meaning
from writing_coach.vocabulary_meaning import saved_word_meaning

CATALOGUE_WORD = {
    "word": "松树",
    "language_code": "zh",
    "definition": "",
    "translation_vi": "",
    "short_meanings": [
        {"language": "en", "text": "pine; pine tree", "origin": "dictionary"},
        {"language": "vi", "text": "cây thông", "origin": "dictionary"},
    ],
}


def test_the_support_language_localization_is_chosen() -> None:
    assert saved_word_meaning(CATALOGUE_WORD, "vi") == "cây thông"
    assert saved_word_meaning(CATALOGUE_WORD, "en") == "pine; pine tree"
    # A support language with no localization falls to another language, not to nothing.
    assert saved_word_meaning(CATALOGUE_WORD, "ja") == "pine; pine tree"


def test_the_learner_note_and_the_older_vietnamese_copy_still_count() -> None:
    assert saved_word_meaning({"definition": "my note"}, "ja") == "my note"
    assert saved_word_meaning({"translation_vi": "khoảng đệm"}, "vi") == "khoảng đệm"
    assert saved_word_meaning({"translation_vi": "khoảng đệm"}, "en") == ""
    assert saved_word_meaning({**CATALOGUE_WORD, "translation_vi": "cũ"}, "vi") == "cây thông"


def test_the_collection_snippet_reads_the_sense_not_only_the_copy(monkeypatch) -> None:
    monkeypatch.setattr(vocabulary_meaning, "_support_language", lambda: "vi")
    [entry] = collection_query.language_entries([CATALOGUE_WORD], "zh")
    assert entry.snippet == "cây thông"
    monkeypatch.setattr(vocabulary_meaning, "_support_language", lambda: "")
    [entry] = collection_query.language_entries([{**CATALOGUE_WORD, "short_meanings": [], "source_fragment": "山上有松树。"}], "zh")
    assert entry.snippet == "山上有松树。"
