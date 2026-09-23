"""Every read of the saved language asks for a page, and says it is a page.

The vocabulary listing became paged; two wirings kept a reference to the
listing function and called it with no arguments. That is no longer "the whole
library" - it is the first default page, reported as everything: the collection
would have shown 50 of 1 619 saved words as a complete result, and the learner
summary would have summed the recalls of those 50 and called it the all-time
total.

So both wirings ask for a bounded page *and* declare the bound. A read that
fills its bound makes that domain's counts a lower bound and its result
partial, which is true; a silent default page is not.
"""
from __future__ import annotations

from typing import Any

from writing_coach.collection_api import LANGUAGE_BOUND as COLLECTION_BOUND, runtime_owners
from writing_coach.learner_summary_api import LANGUAGE_BOUND as SUMMARY_BOUND, runtime_sources


class _Specialized:
    def list_recent_listening_progress_records(self, limit: int) -> list[dict[str, Any]]:
        return []

    def list_speaking_attempt_records(self, limit: int) -> list[dict[str, Any]]:
        return []


def _library_spy(asked: list[int]):
    def read(limit: int, search: str = "") -> dict[str, Any]:
        asked.append(int(limit))
        # More rows than any bound, so a truncating caller would be believed.
        return {"items": [{"word": f"w{index}", "successful_recalls": 1} for index in range(limit)]}

    return read


def test_the_collection_asks_for_a_page_and_declares_it() -> None:
    asked: list[int] = []
    owners = runtime_owners(
        library=_library_spy(asked),
        reading=lambda limit: {"items": []},
        essays=lambda: [],
        specialized=_Specialized(),
        grammar=lambda: [],
    )()
    language = next(owner for owner in owners if owner.domain == "language")
    rows = language.read("")
    # The library holds more than this read takes, so the search goes to it
    # rather than happening after the page comes back.
    assert language.searches is True
    assert asked == [COLLECTION_BOUND]
    assert len(rows) == COLLECTION_BOUND
    assert language.bound == COLLECTION_BOUND


def test_the_learner_summary_asks_for_a_page_and_declares_it() -> None:
    asked: list[int] = []
    sources = runtime_sources(
        essays=lambda: [],
        reading=lambda limit: {"items": []},
        grammar=lambda: set(),
        library=_library_spy(asked),
        specialized=_Specialized(),
    )()
    language = next(source for source in sources if source.domain == "language")
    rows = language.read()
    assert asked == [SUMMARY_BOUND]
    assert len(rows) == SUMMARY_BOUND
    assert language.bound == SUMMARY_BOUND
