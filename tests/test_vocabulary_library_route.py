"""Task D: the Vocabulary Library catalog read routes.

`GET /api/vocabulary/library/collections` and
`GET /api/vocabulary/library/collections/{collection_id}` expose the static
curated catalog (`writing_coach/vocabulary_library.py`) over HTTP. They must
stay clearly distinct from the pre-existing `/api/library/vocabulary`
saved-state routes exercised elsewhere: browsing a collection never creates a
`SavedWord`-equivalent row, and "saved" here is a per-request cross-reference
against the learner's existing saved words
(`SpecializedLearningRepository.list_library_records()`), not a stored
membership flag.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

import app as app_module
from writing_coach.becoming_library import LibraryVocabularyIn
from writing_coach.core.request_context import LANGUAGE_CODE_CTX


def _seed_saved_word(language_code: str, word: str) -> None:
    """Seed one saved word directly through the repository, under an explicit
    language context — bypassing HTTP the way `scripts/run_r16_adaptive_practice.py`
    already does for the same contextvar."""

    token = LANGUAGE_CODE_CTX.set(language_code)
    try:
        app_module.init_db()
        app_module.save_library_vocabulary(
            LibraryVocabularyIn(word=word, definition="seeded", source_kind="manual")
        )
    finally:
        LANGUAGE_CODE_CTX.reset(token)


def _get(path: str) -> httpx.Response:
    async def exercise() -> httpx.Response:
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(exercise())


def test_collections_list_requires_language_code() -> None:
    response = _get("/api/vocabulary/library/collections")
    assert response.status_code == 422


@pytest.mark.parametrize("language_code", ["fr", "xx", "vi"])
def test_collections_list_rejects_unsupported_language_code(language_code: str) -> None:
    response = _get(f"/api/vocabulary/library/collections?language_code={language_code}")
    assert response.status_code == 422


def test_collections_list_is_language_filtered() -> None:
    en = _get("/api/vocabulary/library/collections?language_code=en").json()
    zh = _get("/api/vocabulary/library/collections?language_code=zh").json()
    assert en["items"], "the English catalog should not be empty"
    assert zh["items"], "the Chinese catalog should not be empty"
    assert {item["language_code"] for item in en["items"]} == {"en"}
    assert {item["language_code"] for item in zh["items"]} == {"zh"}
    assert {item["id"] for item in en["items"]} >= {"toeic-600-essential", "common-3000"}
    assert {item["id"] for item in zh["items"]} >= {"hsk-1", "hsk-2"}


def test_unknown_collection_id_is_a_clean_404() -> None:
    response = _get("/api/vocabulary/library/collections/not-a-real-collection")
    assert response.status_code == 404


def test_collection_detail_marks_a_saved_word_and_an_unsaved_word_correctly() -> None:
    _seed_saved_word("en", "invoice")

    response = _get("/api/vocabulary/library/collections/toeic-600-essential")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "toeic-600-essential"
    assert body["language_code"] == "en"
    assert "entries" not in body, "the summary+items shape must not also carry the raw 'entries' key"

    by_word = {item["headword"].casefold(): item for item in body["items"]}
    assert by_word["invoice"]["saved"] is True
    other = next(item for word, item in by_word.items() if word != "invoice")
    assert other["saved"] is False


def test_collection_detail_exposes_derived_review_state_for_management_views() -> None:
    _seed_saved_word("en", "invoice")

    response = _get("/api/vocabulary/library/collections/toeic-600-essential")
    assert response.status_code == 200
    body = response.json()
    invoice = next(item for item in body["items"] if item["headword"].casefold() == "invoice")
    assert invoice["saved"] is True
    assert invoice["review_stage"] == 0
    assert invoice["due"] is True
    assert invoice["successful_recalls"] == 0
    assert invoice["lapse_count"] == 0
    assert body["progress"]["learned_count"] >= 1
    assert body["progress"]["learning_count"] >= 1
    assert body["progress"]["due_count"] >= 1
    assert body["progress"]["mastered_count"] == 0


def test_saved_vocabulary_summary_exposes_overview_state_counts() -> None:
    _seed_saved_word("en", "invoice")

    response = _get("/api/library/vocabulary")
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total"] >= 1
    assert summary["saved"] == summary["total"]
    assert summary["learning"] >= 1
    assert summary["mastered"] == 0
    assert summary["due"] >= 1


def test_saved_catalog_word_reuses_static_card_content_without_new_persistence() -> None:
    _seed_saved_word("en", "invoice")

    response = _get("/api/library/vocabulary")
    assert response.status_code == 200
    invoice = next(item for item in response.json()["items"] if item["word"] == "invoice")
    assert invoice["level"] == "B1"
    assert invoice["framework"] == "toeic"
    assert invoice["phonetic"] == "/ˈɪnvɔɪs/"
    assert invoice["examples"] == [
        {"language": "en", "text": "Please send the invoice before Friday."}
    ]


def test_collection_detail_never_leaks_an_internal_file_path() -> None:
    response = _get("/api/vocabulary/library/collections/hsk-1")
    assert response.status_code == 200
    serialized = response.text
    assert "vocabulary_collections.json" not in serialized
    assert "vocabulary_collections.py" not in serialized
    assert "writing_coach/languages" not in serialized
    assert "writing_coach\\languages" not in serialized
