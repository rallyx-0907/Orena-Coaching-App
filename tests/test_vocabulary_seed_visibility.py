"""F3: learners read vocabulary only through a published collection.

The static seed JSON (`catalog_status: seed`) is authoring material. It must not
reach a learner through the Feed pool, the word-page fallback or search; only
members of a published collection do (D-178 item 3, the collection lifecycle).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

import httpx
import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

import app as app_module  # noqa: E402
from writing_coach import becoming_library, vocabulary_feed, vocabulary_library  # noqa: E402
from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository  # noqa: E402
from writing_coach.vocabulary_source_import import (  # noqa: E402
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)

# Words that exist only in the unpublished static seed.
SEED_EN = "client"
SEED_ZH = "你好"
ADMISSION = {
    "rights_status": "licensed", "completeness": "complete", "review_status": "approved",
    "publication_attested": True, "attested_by": "admin@example.com",
}


def _import(repository, collection_id: str, term: str, status: str = "pending_review") -> None:
    csv = "word,meaning\n" + term + ",nghia\n"
    parsed = parse_vocabulary_source("pack.csv", csv.encode("utf-8"))
    detected = detect_vocabulary_mapping(parsed)
    normalized = normalize_vocabulary_rows(
        parsed, mapping=detected.mapping, language_code="en", meaning_language="vi",
        collection_framework="TOEIC", collection_level="B1",
    )
    repository.import_source(
        collection={
            "id": collection_id, "title": collection_id, "language_code": "en", "framework": "TOEIC",
            "level": "B1", "catalog_status": status, "origin": "imported", "provenance": {"publisher": "test"},
        },
        source=normalized, records=normalized["records"], mapping=detected.mapping, imported_by="admin@example.com",
    )


@pytest.fixture()
def repository(tmp_path, monkeypatch):
    repo = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repo.initialize()
    _import(repo, "live-pack", "zebra")
    repo.finalize_collection_publication("live-pack", admission=ADMISSION)
    _import(repo, "draft-pack", "walrus")
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, vocabulary_repository=repo))
    monkeypatch.setattr(becoming_library, "_content_repository", repo)
    return repo


def _get(path: str) -> httpx.Response:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app), base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(run())


def _headwords(response: httpx.Response) -> set[str]:
    return {str(item.get("headword") or item.get("word") or "").casefold() for item in response.json()["items"]}


def test_the_static_seed_is_not_a_learner_pool() -> None:
    raw = {entry["normalized_word"] for entry in vocabulary_library.all_vocabulary_entries("en")}
    assert SEED_EN in raw, "the seed still exists as authoring material"
    assert vocabulary_library.published_vocabulary_entries("en") == []
    assert vocabulary_library.published_vocabulary_entries("zh") == []
    assert vocabulary_library.vocabulary_entry_for("en", SEED_EN) is None
    assert vocabulary_library.vocabulary_entry_for("zh", SEED_ZH) is None


def test_the_feed_default_pool_is_the_published_one() -> None:
    context = vocabulary_feed.LearnerFeedContext(learner_key="k")
    assert vocabulary_feed.daily_feed_candidates("en", learner_context=context, exclude_normalized=set()) == []


def test_the_feed_route_serves_published_members_only(repository) -> None:
    for language, seed in (("en", SEED_EN),):
        words = _headwords(_get(f"/api/vocabulary/feed?language_code={language}"))
        assert words == {"zebra"}, words
        assert seed not in words and "walrus" not in words


def test_the_feed_serves_no_seed_for_chinese_either(repository) -> None:
    assert _get("/api/vocabulary/feed?language_code=zh").json()["items"] == []


def test_the_word_page_fallback_ignores_seed_and_unpublished_entries(repository) -> None:
    assert becoming_library.catalog_entry_for(SEED_EN) is None
    assert becoming_library.catalog_entry_for("walrus") is None
    assert (becoming_library.catalog_entry_for("zebra") or {}).get("term") == "zebra"


def test_search_returns_published_members_only(repository) -> None:
    for query, expected in (("zeb", ["zebra"]), ("walr", []), ("clie", [])):
        items = _get(f"/api/vocabulary/catalogue/search?q={query}&language_code=en").json()["items"]
        assert [item["word"] for item in items] == expected, query


def test_a_published_static_collection_would_still_reach_learners(monkeypatch) -> None:
    """The gate is the collection's status, not a blanket ban on the static source."""

    raw = {cid: dict(c, catalog_status="published") for cid, c in vocabulary_library._CATALOG_BY_ID.items() if cid == "toeic-600-essential"}
    learner = vocabulary_library._build_learner_catalog(raw)
    monkeypatch.setattr(vocabulary_library, "_LEARNER_CATALOG_BY_ID", learner)
    monkeypatch.setattr(vocabulary_library, "_LEARNER_ENTRY_INDEX", vocabulary_library._build_entry_index(learner))
    assert vocabulary_library.vocabulary_entry_for("en", SEED_EN) is not None
    assert any(e["normalized_word"] == SEED_EN for e in vocabulary_library.published_vocabulary_entries("en"))
