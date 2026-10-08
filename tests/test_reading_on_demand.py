"""Reading on demand: translation, summary and contextual meaning are generated when asked, once, and kept.

No network and no provider: every engine here is a fake that counts its calls.
`ORENA_TEST_POSTGRES_URL` names a throwaway database for the PostgreSQL proof of the proposed migration
20261005_0028 (applied and rolled back by hand: it is not in the Alembic chain yet).
"""

from __future__ import annotations

import importlib.util
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from writing_coach import media_interaction, reading_translation_api, word_detail
from writing_coach.core.http_security import rate_group
from writing_coach.media_translation import TranslationProviderError
from writing_coach.reading_derived import DerivedCache, normalize_text
from writing_coach.reading_summary import ReadingSummaryService, SummaryUnavailable
from writing_coach.reading_translation import (
    PlatformAITranslationProvider,
    ReadingTranslationService,
    TextSegment,
)

NOON = datetime(2026, 10, 5, 12, tzinfo=UTC)


class MemoryStore:
    """A stand-in for the PostgreSQL table, keyed the way the table is."""

    def __init__(self, *, fail: bool = False) -> None:
        self.rows: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.fail = fail
        self.reads = 0

    def get_many(self, kind, target_language, keys):
        self.reads += 1
        if self.fail:
            raise RuntimeError("relation reading_derived_texts does not exist")
        return {key: self.rows[(kind, target_language, key)] for key in keys if (kind, target_language, key) in self.rows}

    def put_many(self, kind, target_language, source_language, rows, *, provider, model):
        if self.fail:
            raise RuntimeError("relation reading_derived_texts does not exist")
        for key, payload in rows:
            self.rows.setdefault((kind, target_language, key), payload)


class CountingEngine:
    engine_id = "fake"
    model_version = "fake-1"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.fail = fail

    def translate_batch(self, source_language, target_language, segments):
        self.calls.append([item.original_text for item in segments])
        if self.fail:
            raise TranslationProviderError("down")
        return {item.segment_id: f"{target_language}|{item.original_text}" for item in segments}


# ---- translation -----------------------------------------------------------------------------------------


def test_a_sentence_is_generated_once_for_the_reader_and_the_sentence_sheet() -> None:
    engine = CountingEngine()
    service = ReadingTranslationService(engine)
    reader = service.translate("en", "vi", [TextSegment("p3s1", "It rained."), TextSegment("p3s2", "We  stayed in.")])
    sheet = service.translate("en", "vi", [TextSegment("only", " We stayed\nin. ")])  # another id, same sentence

    assert reader.translations[1][1] == sheet.translations[0][1] == "vi|We  stayed in."
    assert engine.calls == [["It rained.", "We  stayed in."]]  # the sheet cost nothing


def test_the_key_is_the_text_and_languages_not_the_segment_id() -> None:
    engine = CountingEngine()
    service = ReadingTranslationService(engine)
    service.translate("en", "vi", [TextSegment("a", "Hello.")])
    service.translate("en", "vi", [TextSegment("b", "Hello.")])
    service.translate("en", "es", [TextSegment("a", "Hello.")])
    assert engine.calls == [["Hello."], ["Hello."]]  # the second language is its own entry


def test_published_text_survives_a_restart_through_the_shared_table() -> None:
    store = MemoryStore()
    first = ReadingTranslationService(CountingEngine(), cache=DerivedCache(store))
    first.translate("en", "vi", [TextSegment("a", "It rained.")], persist=True)
    engine = CountingEngine()
    restarted = ReadingTranslationService(engine, cache=DerivedCache(store))
    result = restarted.translate("en", "vi", [TextSegment("z", "It rained.")], persist=True)
    assert result.translations == (("z", "vi|It rained."),) and engine.calls == []


def test_a_learners_own_text_never_reaches_the_shared_table() -> None:
    store = MemoryStore()
    service = ReadingTranslationService(CountingEngine(), cache=DerivedCache(store))
    service.translate("en", "vi", [TextSegment("a", "My private diary line.")])  # persist defaults to off
    assert store.rows == {} and store.reads == 0


def test_a_missing_table_pauses_persistence_and_the_learner_is_still_served() -> None:
    clock = [NOON]
    store = MemoryStore(fail=True)
    cache = DerivedCache(store, now=lambda: clock[0])
    engine = CountingEngine()
    service = ReadingTranslationService(engine, cache=cache)
    assert service.translate("en", "vi", [TextSegment("a", "One.")], persist=True).translations
    reads = store.reads
    service.translate("en", "vi", [TextSegment("b", "Two.")], persist=True)
    assert store.reads == reads  # paused: the table is not asked again
    clock[0] = NOON + timedelta(minutes=5)
    store.fail = False
    service.translate("en", "vi", [TextSegment("c", "Three.")], persist=True)
    assert store.reads == reads + 1 and ("translation", "vi") in {(k[0], k[1]) for k in store.rows}


def test_a_provider_error_is_not_cached_so_the_retry_calls_again() -> None:
    engine = CountingEngine(fail=True)
    service = ReadingTranslationService(engine)
    assert service.translate("en", "vi", [TextSegment("a", "One.")]).status.value == "unavailable"
    engine.fail = False
    assert service.translate("en", "vi", [TextSegment("a", "One.")]).status.value == "ready"
    assert len(engine.calls) == 2


def test_the_ai_engine_asks_the_platform_capability_once_per_batch_and_reads_its_answer() -> None:
    seen: list[dict[str, Any]] = []

    def generate(**kwargs: Any) -> dict[str, Any]:
        seen.append(kwargs)
        return {"translations": [{"id": "a", "text": "Trời mưa."}, {"id": "b", "text": "Chúng tôi ở nhà."}]}

    service = ReadingTranslationService(PlatformAITranslationProvider(generate))
    result = service.translate("en", "vi", [TextSegment("a", "It rained."), TextSegment("b", "We stayed in.")])
    assert result.translations == (("a", "Trời mưa."), ("b", "Chúng tôi ở nhà.")) and len(seen) == 1
    assert "Vietnamese" in seen[0]["messages"][0]["content"]
    assert service.uses_ai is True


def test_a_malformed_ai_answer_is_unavailable_not_half_served() -> None:
    service = ReadingTranslationService(PlatformAITranslationProvider(lambda **_k: {"translations": [{"id": "a", "text": "x"}]}))
    result = service.translate("en", "vi", [TextSegment("a", "One."), TextSegment("b", "Two.")])
    assert result.status.value == "unavailable" and result.translations == ()


# ---- summary ----------------------------------------------------------------------------------------------


class CountingSummary:
    def __init__(self, bullets=None, *, fail=False) -> None:
        self.calls = 0
        self.bullets = bullets if bullets is not None else ["One.", "Two.", "Three."]
        self.fail = fail

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls += 1
        if self.fail:
            raise SummaryUnavailable("down")
        return {"bullets": list(self.bullets)}


def test_a_summary_is_generated_once_per_text_and_target() -> None:
    generate = CountingSummary()
    service = ReadingSummaryService(DerivedCache(), generate)
    first = service.summarize("A long\n text.", "en", "vi", persist=False)
    again = service.summarize("A long text.", "en", "vi", persist=False)
    assert first == again == ["One.", "Two.", "Three."] and generate.calls == 1
    service.summarize("A long text.", "en", "zh", persist=False)
    assert generate.calls == 2


def test_a_failed_or_empty_summary_is_retryable_and_not_cached() -> None:
    generate = CountingSummary(fail=True)
    service = ReadingSummaryService(DerivedCache(), generate)
    with pytest.raises(SummaryUnavailable):
        service.summarize("Text.", "en", "vi", persist=False)
    generate.fail = False
    assert service.summarize("Text.", "en", "vi", persist=False)
    assert generate.calls == 2
    empty = ReadingSummaryService(DerivedCache(), CountingSummary(bullets=[" "]))
    with pytest.raises(SummaryUnavailable):
        empty.summarize("Text.", "en", "vi", persist=False)


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: "en")
    generate = CountingSummary()
    reading_translation_api.configure_reading_summary(ReadingSummaryService(DerivedCache(), generate))
    app = FastAPI()
    app.include_router(reading_translation_api.router)
    yield TestClient(app), generate
    reading_translation_api.configure_reading_summary(None)


def test_nothing_is_generated_until_summary_is_requested(api) -> None:
    _http, generate = api
    assert generate.calls == 0  # opening a text reaches no summary code at all


def test_the_summary_endpoint_returns_bullets_and_reuses_them(api) -> None:
    http, generate = api
    body = {"source_language": "en", "target_language": "vi", "text": "It rained all day and we stayed in."}
    first = http.post("/api/reading/summary", json=body)
    second = http.post("/api/reading/summary", json=body)
    assert first.status_code == 200 and first.json()["bullets"] == ["One.", "Two.", "Three."]
    assert second.json() == first.json() and generate.calls == 1


def test_the_summary_endpoint_names_exactly_one_text(api) -> None:
    http, generate = api
    base = {"source_language": "en", "target_language": "vi"}
    assert http.post("/api/reading/summary", json=base).status_code == 422
    assert http.post("/api/reading/summary", json={**base, "text": "x", "article_id": "a1"}).status_code == 422
    assert http.post("/api/reading/summary", json={**base, "book_id": "b1"}).status_code == 422
    assert generate.calls == 0


def test_the_summary_endpoint_answers_a_provider_failure_as_retryable(api) -> None:
    http, generate = api
    generate.fail = True
    response = http.post(
        "/api/reading/summary", json={"source_language": "en", "target_language": "vi", "text": "Some text."}
    )
    assert response.status_code == 503
    assert response.json()["detail"]["retryable"] is True


def test_a_published_article_is_summarised_by_id_and_may_persist(api, monkeypatch) -> None:
    http, generate = api
    from writing_coach import reading_articles_api

    class Repo:
        def get_published_article(self, article_id):
            return {"id": article_id, "body": "Published body."}

    monkeypatch.setattr(reading_articles_api, "_repository", Repo())
    response = http.post(
        "/api/reading/summary", json={"source_language": "en", "target_language": "vi", "article_id": "abc"}
    )
    assert response.status_code == 200 and generate.calls == 1


def test_the_new_routes_are_in_the_reading_rate_group() -> None:
    assert rate_group("POST", "/api/reading/summary")[0] == "reading_ai"
    assert rate_group("POST", "/api/reading/translate")[0] == "reading_ai"


def test_translate_endpoint_persists_only_for_a_published_article(monkeypatch) -> None:
    store = MemoryStore()
    monkeypatch.setattr(reading_translation_api, "current_language_code", lambda: "en")
    reading_translation_api.configure_reading_translation(
        ReadingTranslationService(CountingEngine(), cache=DerivedCache(store))
    )
    app = FastAPI()
    app.include_router(reading_translation_api.router)
    http = TestClient(app)
    body = {"source_language": "en", "target_language": "vi", "segments": [{"segment_id": "p1s1", "text": "Hello."}]}
    try:
        assert http.post("/api/reading/translate", json=body).status_code == 200
        assert store.rows == {}
        assert http.post("/api/reading/translate", json={**body, "content_id": "book:b1:c1"}).status_code == 200
        assert store.rows == {}  # a book chapter is a learner's import: process memory only
        assert http.post("/api/reading/translate", json={**body, "content_id": "article:abc", "segments": [{"segment_id": "p1s1", "text": "Goodbye."}]}).status_code == 200
        assert len(store.rows) == 1
    finally:
        reading_translation_api.configure_reading_translation(None)


# ---- contextual meaning (word-detail / sentence-sheet) ----------------------------------------------------


@pytest.fixture
def sheet(monkeypatch):
    monkeypatch.setattr(media_interaction, "current_language_code", lambda: "en")
    monkeypatch.setattr(word_detail, "_lookup", None)
    monkeypatch.setattr(word_detail, "_saved_terms", None)
    store = MemoryStore()
    monkeypatch.setattr(word_detail, "_cache", DerivedCache(store))
    calls: list[str] = []
    state = {"fail": False}

    def structured(capability_key, *, messages, schema, max_output_tokens):
        calls.append(capability_key)
        if state["fail"]:
            raise HTTPException(503, "down")
        if "why_here" in schema["properties"]:
            return {"context_meaning": "ran out", "why_here": "The lamp is the thing that stopped."}
        return {"summary": "Went dark.", "natural_translation": "It went dark.", "structure": [], "vocabulary": []}

    monkeypatch.setattr(media_interaction, "_run_structured", structured)
    return calls, state, store


def _word(**over: Any) -> dict[str, Any]:
    body = {"text": "ran out", "context": "The lamp ran out of oil.", "source_language": "en",
            "target_language": "vi", "depth": "sheet"}  # fmt: skip
    return word_detail.word_detail(word_detail.WordDetailIn(**{**body, **over}))


def test_the_sheet_leads_with_the_meaning_here_and_a_short_why(sheet) -> None:
    calls, _state, _store = sheet
    body = _word()
    assert body["contextMeaning"] == "ran out" and body["meaningSource"] == "context"
    assert body["deeper"]["whyHere"] == "The lamp is the thing that stopped."
    assert body["contextStatus"] == "ready" and body["retryable"] is False and calls == ["learner_dictionary"]


def test_the_same_word_in_the_same_sentence_asks_the_provider_once(sheet) -> None:
    calls, _state, store = sheet
    _word()
    _word(context="The  lamp ran out of oil.")  # whitespace is not a different sentence
    assert calls == ["learner_dictionary"] and store.rows == {}  # no content id: process memory only


def test_published_content_is_kept_in_the_shared_table(sheet) -> None:
    _calls, _state, store = sheet
    _word(content_id="article:abc")
    assert [key[0] for key in store.rows] == ["gloss"]


def test_a_provider_failure_is_retryable_and_never_cached(sheet) -> None:
    calls, state, _store = sheet
    state["fail"] = True
    body = _word()
    assert body["contextStatus"] == "provider_error" and body["retryable"] is True
    assert body["available"] is False  # nothing else answered: not "no contextual meaning", an error to retry
    state["fail"] = False
    assert _word()["contextStatus"] == "ready" and len(calls) == 2


def test_the_sentence_sheet_is_cached_but_the_learners_question_never_is(sheet, monkeypatch) -> None:
    calls, _state, store = sheet
    sentence = word_detail.SentenceSheetIn(
        text="The lamp ran out of oil.", source_language="en", target_language="vi", content_id="article:abc"
    )
    assert word_detail.sentence_sheet(sentence)["available"] is True
    word_detail.sentence_sheet(sentence)
    assert len(calls) == 1
    assert [key[0] for key in store.rows] == ["explanation"]

    tutor_calls: list[str] = []
    asked = word_detail.SentenceSheetIn(
        text="The lamp ran out of oil.", source_language="en", target_language="vi",
        content_id="article:abc", question="why ran out?",
    )  # fmt: skip

    def tutor(capability_key, **_k):
        tutor_calls.append(capability_key)
        return {"answer": "Because.", "follow_ups": []}

    monkeypatch.setattr(media_interaction, "_run_structured", tutor)
    word_detail.sentence_sheet(asked)
    word_detail.sentence_sheet(asked)
    assert len(tutor_calls) == 2 and [key[0] for key in store.rows] == ["explanation"]


def test_normalize_text_folds_whitespace_and_unicode_form() -> None:
    assert normalize_text(" a \n b ") == "a b"
    assert normalize_text("é") == normalize_text("é")


# ---- PostgreSQL proof of the proposed migration ---------------------------------------------------------------

URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "proposed" / "20261005_0028_reading_derived_texts.py"


def _proposed_migration():
    spec = importlib.util.spec_from_file_location("proposed_0028", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_proposed_migration_is_parented_on_the_billing_proposal() -> None:
    assert _proposed_migration().down_revision == "20261005_0027"


@pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
def test_postgres_stores_once_reads_back_and_rolls_back() -> None:
    pytest.importorskip("alembic")
    from alembic import command
    from alembic.config import Config
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, func, select, text
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.orm import Session

    from writing_coach.persistence.models import ReadingDerivedText
    from writing_coach.persistence.reading_derived_repository import ReadingDerivedRepository

    schema = f"reading_derived_{uuid.uuid4().hex[:10]}"
    separator = "&" if "?" in URL else "?"
    schema_url = f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"
    admin = create_engine(URL, future=True)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("sqlalchemy.url", schema_url.replace("%", "%%"))
        command.upgrade(cfg, "head")
        engine = create_engine(schema_url, future=True)
        migration = _proposed_migration()
        try:
            repository = ReadingDerivedRepository(engine)
            cache = DerivedCache(repository, now=lambda: NOON)
            key = "a" * 64
            # Before the table: an error the cache absorbs, never the learner's failure.
            with pytest.raises(DBAPIError):
                repository.get_many("translation", "vi", [key])
            assert cache.get("translation", "vi", key, persist=True) is None
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            repository.put_many("translation", "vi", "en", [(key, {"text": "first"})], provider="ai", model="m")
            repository.put_many("translation", "vi", "en", [(key, {"text": "second"})], provider="ai", model="m")
            assert repository.get_many("translation", "vi", [key]) == {key: {"text": "first"}}  # first writer wins
            assert repository.get_many("translation", "zh", [key]) == {}  # per support language
            repository.put_many("summary", "vi", "en", [(key, {"bullets": ["x"]})], provider="", model="")
            with Session(engine) as session:
                assert session.scalar(select(func.count(ReadingDerivedText.content_hash))) == 2
            with pytest.raises(DBAPIError):
                repository.put_many("bogus", "vi", "en", [(key, {})], provider="", model="")
            with pytest.raises(DBAPIError):
                repository.put_many("summary", "vi", "en", [("short", {})], provider="", model="")
            with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
                migration.downgrade()
            with pytest.raises(DBAPIError):
                repository.get_many("translation", "vi", [key])
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
