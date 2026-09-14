"""Task A1: `LibraryVocabularyIn.source_kind` accepts the truthful values the
system already needs — `reading` (existing repository/card usage), and the
new `feed` (Daily Feed keep) and `collection` (Library-browsing save) — while
still rejecting an unrecognized kind such as `listening`.

`LibraryVocabularyIn` is the Pydantic contract FastAPI validates
`POST /api/library/vocabulary` against before the handler runs; a value this
model rejects is exactly the value that endpoint answers 422 for.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from writing_coach.becoming_library import LibraryVocabularyIn


@pytest.mark.parametrize("source_kind", ["manual", "dictionary", "feedback", "strength", "reading", "feed", "collection"])
def test_accepts_every_truthful_source_kind(source_kind: str) -> None:
    payload = LibraryVocabularyIn(word="harbour", source_kind=source_kind)
    assert payload.source_kind == source_kind


def test_rejects_unrecognized_source_kind() -> None:
    with pytest.raises(ValidationError):
        LibraryVocabularyIn(word="harbour", source_kind="listening")


def test_default_source_kind_is_manual() -> None:
    payload = LibraryVocabularyIn(word="harbour")
    assert payload.source_kind == "manual"
