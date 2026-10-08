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
from copy import deepcopy

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
    # Current JSON packs are explicitly seed-sized.  The learner route must
    # stay empty until a content owner marks a coherent pack published,
    # rather than presenting 2/3/35 entries as finished collections.
    assert en["items"] == []
    assert zh["items"] == []


def test_unknown_collection_id_is_a_clean_404() -> None:
    response = _get("/api/vocabulary/library/collections/not-a-real-collection")
    assert response.status_code == 404


def test_unpublished_collection_detail_is_not_learner_visible() -> None:
    response = _get("/api/vocabulary/library/collections/toeic-600-essential")
    assert response.status_code == 404


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


def test_unpublished_collection_detail_never_leaks_an_internal_file_path() -> None:
    response = _get("/api/vocabulary/library/collections/hsk-1")
    assert response.status_code == 404
    serialized = response.text
    assert "vocabulary_collections.json" not in serialized
    assert "vocabulary_collections.py" not in serialized
    assert "writing_coach/languages" not in serialized
    assert "writing_coach\\languages" not in serialized


@pytest.mark.parametrize("language,word", [("en", "invoice"), ("zh", "书")])
def test_collection_review_projects_only_its_saved_rows_without_provider_work(monkeypatch, language, word):
    entry = {"word": word, "normalized_word": word, "language_code": language,
             "definition": "persisted source meaning"}
    catalog = {"id": "review-pack", "language_code": language, "item_count": 1,
               "entries": [entry]}
    calls = []

    def saved(candidates):
        assert LANGUAGE_CODE_CTX.get() == language
        calls.append(candidates)
        return {word: {"word": word, "review_stage": 3, "next_review_at": "2099-01-01",
                       "due": False, "schedule": {"got_it": {"days": 21}}}}

    monkeypatch.setattr(app_module, "_persisted_vocabulary_collection", lambda *a, **k: deepcopy(catalog))
    monkeypatch.setattr(app_module, "saved_vocabulary_state", saved)
    monkeypatch.setattr(app_module, "save_library_vocabulary", lambda *a, **k: pytest.fail("opening must not save"))
    ordinary = _get("/api/vocabulary/library/collections/review-pack").json()
    assert "review_items" not in ordinary
    for _ in range(2):
        response = _get("/api/vocabulary/library/collections/review-pack?include_review=true")
        assert response.status_code == 200
        row = response.json()["review_items"][0]
        assert row["word"] == word
        assert row["review_stage"] == 3
        assert row["next_review_at"] == "2099-01-01"
    assert calls == [(word,)] * 3


def test_collection_review_does_not_limit_members_to_first_200_saved_words(monkeypatch):
    entries = [{"word": f"term{n}", "normalized_word": f"term{n}", "language_code": "en"}
               for n in range(205)]
    catalog = {"id": "large-pack", "language_code": "en", "item_count": len(entries), "entries": entries}
    monkeypatch.setattr(app_module, "_persisted_vocabulary_collection", lambda *a, **k: deepcopy(catalog))
    monkeypatch.setattr(app_module, "saved_vocabulary_state", lambda candidates:
                        {word: {"word": word, "review_stage": 1} for word in candidates})
    response = _get("/api/vocabulary/library/collections/large-pack?include_review=true&limit=5000")
    assert response.status_code == 200
    rows = response.json()["review_items"]
    assert len(rows) == 205
    assert rows[-1]["word"] == "term204"
