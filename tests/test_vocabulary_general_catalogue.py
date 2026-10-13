# ruff: noqa: F811 - fixtures imported by name from tests/test_vocabulary_ingest_token.py are used as test arguments
"""The derived "General catalogue" (D-188, docs/reviews/architecture/VOCAB_GENERAL_CATALOGUE_DESIGN_2026-10-13.md).

What must hold: a word is in General(L) only through a published collection of language L whose admission passes the
publish gate; it leaves the moment its last such collection stops qualifying; nothing is stored; the reserved id cannot
be created by any import path; and nothing that enumerates real collections can see General.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import httpx
import pytest

import app as app_module
from tests.test_vocabulary_ingest_token import (  # noqa: F401 - fixtures used by name
    IMPORT,
    TOKEN,
    call,
    csv_file,
    csv_import_data,
    repository as token_repository,
    secured,
    token_on,
)
from writing_coach import policies
from writing_coach.persistence import vocabulary_repository as vr
from writing_coach.persistence.vocabulary_repository import (
    GENERAL_FALLBACK_TITLE,
    GENERAL_SYSTEM_KIND,
    VOCABULARY_REQUIRED_COLUMNS,
    general_collection_language,
    is_reserved_collection_id,
    sqlite_vocabulary_repository,
)
from writing_coach.vocabulary_source_import import (
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)

VALID = {
    "review_status": "approved",
    "publication_attested": True,
    "attested_by": "test-admin",
    "rights_status": "licensed",
    "completeness": "complete",
}


@pytest.fixture()
def repo(tmp_path):
    repository = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repository.initialize()
    return repository


def make_set(repository, collection_id, terms, *, language="en", admission=None, status="published", provenance=None,
             levels=None):
    """Import `terms` into a set. `admission` None means the valid one; `provenance` replaces the whole record."""

    rows = "English|Vietnamese|Level\n" + "".join(
        f"{term}|nghĩa {term}|{(levels or {}).get(term, 'A1')}\n" for term in terms
    )
    parsed = parse_vocabulary_source("w.csv", rows.encode("utf-8"))
    mapping = detect_vocabulary_mapping(parsed).mapping
    normalized = normalize_vocabulary_rows(parsed, mapping=mapping, language_code=language, meaning_language="vi")
    record = provenance if provenance is not None else {"admission": dict(VALID if admission is None else admission)}
    repository.import_source(
        collection={"id": collection_id, "title": collection_id, "language_code": language,
                    "catalog_status": "pending_review", "origin": "imported", "provenance": record},
        source=normalized, records=normalized["records"], mapping=mapping, imported_by="test",
    )
    if status != "pending_review":
        _force_status(repository, collection_id, status)


def _force_status(repository, collection_id, status):
    from sqlalchemy.orm import Session

    from writing_coach.persistence.models import VocabularyCollection

    with Session(repository.engine) as session, session.begin():
        session.get(VocabularyCollection, collection_id).catalog_status = status


def _force_provenance(repository, collection_id, provenance):
    from sqlalchemy import text

    with repository.engine.begin() as connection:
        connection.execute(text("UPDATE vocabulary_collections SET provenance = :p WHERE id = :i"),
                           {"p": json.dumps(provenance), "i": collection_id})


def general_terms(repository, language="en", **kwargs):
    page = repository.general_page(language, limit=kwargs.pop("limit", 5000), **kwargs)
    return None if page is None else [entry["term"] for entry in page["entries"]]


# ------------------------------------------------------------------------------------------------ membership rule


def test_only_a_published_set_with_a_valid_admission_contributes(repo) -> None:
    make_set(repo, "pub", ["alpha", "beta"])
    make_set(repo, "pending", ["gamma"], status="pending_review")
    make_set(repo, "off", ["delta"], status="unpublished")
    make_set(repo, "gone", ["epsilon"], status="archived")
    assert general_terms(repo) == ["alpha", "beta"]
    summary = repo.general_summary("en")
    assert summary["item_count"] == 2 and summary["system_kind"] == GENERAL_SYSTEM_KIND
    assert summary["id"] == "orena-general-en" and summary["title"] == GENERAL_FALLBACK_TITLE


def test_a_word_stays_through_its_published_set_and_leaves_with_the_last_one(repo) -> None:
    make_set(repo, "a", ["shared", "only-a"])
    make_set(repo, "b", ["shared", "only-b"], status="unpublished")
    assert general_terms(repo) == ["only-a", "shared"], "an unpublished second set neither adds nor removes"
    repo.set_collection_status("a", "unpublished", actor="mod")
    assert repo.general_page("en") is None and repo.general_summary("en") is None, "withdrawn: nothing comes back"
    _force_status(repo, "a", "published")
    assert general_terms(repo) == ["only-a", "shared"], "republished: back, because it is derived"


@pytest.mark.parametrize("label,admission", [
    ("unattested", {**VALID, "publication_attested": False}),
    ("truthy string", {**VALID, "publication_attested": "true"}),
    ("whitespace reviewer", {**VALID, "attested_by": "   "}),
    ("rights unknown", {**VALID, "rights_status": "unknown"}),
    ("incomplete", {**VALID, "completeness": "partial"}),
    ("not approved", {**VALID, "review_status": "pending_review"}),
])
def test_a_published_set_whose_admission_fails_the_publish_gate_contributes_nothing(repo, label, admission) -> None:
    make_set(repo, "bad", ["x"], admission=admission)
    make_set(repo, "good", ["ok"])
    assert general_terms(repo) == ["ok"], label
    assert [c["id"] for c in repo.list_collections("en")] == ["bad", "good"], "the set itself is still listed"


@pytest.mark.parametrize("stored", [None, "a string", {}, {"admission": "x"}, {"admission": None}, [1]])
def test_malformed_provenance_never_breaks_a_read_and_a_valid_sibling_is_still_listed(repo, stored) -> None:
    make_set(repo, "broken", ["x"])
    make_set(repo, "good", ["ok"])
    _force_provenance(repo, "broken", stored)
    assert general_terms(repo) == ["ok"]
    assert repo.general_summary("en")["item_count"] == 1


def test_the_d111_auto_published_admission_counts(repo) -> None:
    make_set(repo, "auto", ["rule"], admission={**VALID, "attested_by": "orena:auto-publish (D-111)", "auto_published": True})
    assert general_terms(repo) == ["rule"]


def test_a_service_token_set_does_not_qualify_until_a_human_publishes_it(repo) -> None:
    pending_admission = {"rights_status": "unknown", "completeness": "partial", "review_status": "pending_review",
                         "publication_attested": False}
    make_set(repo, "t", ["from-token"], status="pending_review", admission=pending_admission)
    assert repo.general_page("en") is None
    repo.finalize_collection_publication("t", admission=VALID)
    assert general_terms(repo) == ["from-token"]


def test_languages_are_isolated_and_a_crafted_cross_language_membership_is_in_neither(repo) -> None:
    make_set(repo, "en-set", ["alpha"])
    make_set(repo, "zh-set", ["学习"], language="zh")
    assert general_terms(repo, "en") == ["alpha"] and general_terms(repo, "zh") == ["学习"]
    assert repo.general_page("ja") is None
    # an English entry placed (by hand) in the Chinese set belongs to neither General
    from sqlalchemy.orm import Session

    from writing_coach.persistence.models import VocabularyCollectionMembership, VocabularyEntry
    import uuid

    with Session(repo.engine) as session, session.begin():
        entry = session.query(VocabularyEntry).filter_by(normalized_term="alpha").one()
        session.add(VocabularyCollectionMembership(id=uuid.uuid4(), collection_id="zh-set", entry_id=entry.id, position=9,
                                                   membership_metadata={}))
        session.query(VocabularyCollectionMembership).filter_by(collection_id="en-set").delete()
    assert general_terms(repo, "en") is None
    assert general_terms(repo, "zh") == ["学习"]


def test_an_orphan_entry_is_never_listed(repo) -> None:
    make_set(repo, "a", ["alpha"])
    from sqlalchemy import text

    with repo.engine.begin() as connection:
        connection.execute(text("DELETE FROM vocabulary_collection_memberships"))
    assert repo.general_page("en") is None


def test_an_entry_in_two_published_sets_appears_once(repo) -> None:
    make_set(repo, "a", ["shared", "x"])
    make_set(repo, "b", ["shared", "y"])
    assert general_terms(repo) == ["shared", "x", "y"]
    assert repo.general_summary("en")["item_count"] == 3


def test_withdrawal_is_by_set_not_by_content_and_this_is_pinned(repo) -> None:
    """D-188 / review P1-5: an entry first created by set B (later withdrawn) and then included in published set A is in
    General with B's text. The entry row is shared and has no rights field. A later fix is a deliberate change."""

    def put(collection_id, header, row, status, admission):
        parsed = parse_vocabulary_source("w.csv", f"{header}\n{row}\n".encode())
        mapping = detect_vocabulary_mapping(parsed).mapping
        normalized = normalize_vocabulary_rows(parsed, mapping=mapping, language_code="en", meaning_language="vi")
        repo.import_source(collection={"id": collection_id, "title": collection_id, "language_code": "en",
                                       "catalog_status": "pending_review", "origin": "imported",
                                       "provenance": {"admission": admission}},
                           source=normalized, records=normalized["records"], mapping=mapping, imported_by="t")
        _force_status(repo, collection_id, status)

    put("b", "English|Vietnamese|Definition", "shared|chung|a definition written only in set B", "unpublished", dict(VALID))
    put("a", "English|Vietnamese", "shared|chung", "published", dict(VALID))
    entry = repo.general_page("en")["entries"][0]
    assert entry["term"] == "shared"
    assert any("only in set B" in d.get("text", "") for d in entry["detailed_definitions"]), (
        "B's text is still what General shows: withdrawal is by set"
    )


# ----------------------------------------------------------------------------------------------------- query shape


def test_paging_is_total_and_spans_chunk_boundaries(repo, monkeypatch) -> None:
    monkeypatch.setattr(vr, "_GENERAL_ID_CHUNK", 2)  # the multi-chunk path runs here, not only in production
    for index in range(5):
        make_set(repo, f"set-{index}", [f"w{index}a", f"w{index}b", f"w{index}c"])
    first = repo.general_page("en", limit=4, offset=0)
    pages = [first]
    while pages[-1]["pagination"]["has_more"]:
        pages.append(repo.general_page("en", limit=4, offset=len(pages) * 4))
    terms = [e["term"] for page in pages for e in page["entries"]]
    assert len(terms) == len(set(terms)) == 15 and first["pagination"]["total"] == 15
    assert [e["position"] for e in first["entries"]] == [1, 2, 3, 4]
    # an unpublish between page 1 and page 2: no error, and the total reflects the new state
    repo.set_collection_status("set-0", "unpublished", actor="mod")
    second = repo.general_page("en", limit=4, offset=4)
    assert second["pagination"]["total"] == 12 and len({e["term"] for e in second["entries"]}) == 4


def test_search_and_level_filters_use_the_entry_level_only(repo) -> None:
    make_set(repo, "a", ["alpha", "beta"], levels={"alpha": "A1", "beta": "B2"})
    assert general_terms(repo, search="alp") == ["alpha"]
    assert general_terms(repo, level="b2") == ["beta"]
    assert repo.general_summary("en")["levels"] == ["A1", "B2"]


def test_the_cap_is_a_failure_not_a_silent_truncation(repo, monkeypatch) -> None:
    monkeypatch.setattr(vr, "_GENERAL_ID_LIMIT", 1)
    make_set(repo, "a", ["alpha"])
    make_set(repo, "b", ["beta"])
    with pytest.raises(vr.VocabularyContentUnavailable):
        repo.general_summary("en")


def test_general_contains_answers_only_for_the_words_asked(repo, monkeypatch) -> None:
    monkeypatch.setattr(vr, "_GENERAL_TERM_CHUNK", 2)
    make_set(repo, "a", ["alpha", "beta", "gamma"])
    assert repo.general_contains("en", ["beta", "gamma", "nope", "alpha"]) == {"alpha", "beta", "gamma"}
    assert repo.general_contains("en", ["nope"]) == set() and repo.general_contains("en", []) == set()


def test_nothing_is_stored_and_the_schema_is_unchanged(repo) -> None:
    make_set(repo, "a", ["alpha"])
    before = {c["id"] for c in repo.list_collections("en", status=None)}
    repo.general_summary("en")
    repo.general_page("en")
    assert {c["id"] for c in repo.list_collections("en", status=None)} == before == {"a"}
    assert VOCABULARY_REQUIRED_COLUMNS["vocabulary_collections"] >= {"id", "provenance", "catalog_status"}
    assert vr.VOCABULARY_SCHEMA_REVISION == "20260916_0008", "no migration"


def test_the_summary_and_the_page_carry_no_provenance_or_reviewer(repo) -> None:
    make_set(repo, "a", ["alpha"])
    text_ = json.dumps([repo.general_summary("en"), repo.general_page("en")["pagination"]], ensure_ascii=False)
    assert "attested_by" not in text_ and "test-admin" not in text_ and "provenance" not in text_


def test_real_collection_reads_never_include_general(repo) -> None:
    make_set(repo, "a", ["alpha"])
    for status in ("published", None):
        assert all(not is_reserved_collection_id(c["id"]) for c in repo.list_collections("en", status=status))
    assert repo.get_collection("orena-general-en", status=None) is None


# ---------------------------------------------------------------------------------------------------- reserved id


@pytest.mark.parametrize("spelling", [
    "orena-general-en", "ORENA-General-en", " orena-general-en", "orena-general-en ", "ｏｒｅｎａ－ｇｅｎｅｒａｌ－ｅｎ",
    "orena-general-", "orena-general-xx",
])
def test_import_source_refuses_every_spelling_of_the_reserved_id(repo, spelling) -> None:
    parsed = parse_vocabulary_source("w.csv", b"English|Vietnamese\nhello|xin chao\n")
    mapping = detect_vocabulary_mapping(parsed).mapping
    normalized = normalize_vocabulary_rows(parsed, mapping=mapping, language_code="en", meaning_language="vi")
    with pytest.raises(ValueError, match="General catalogue"):
        repo.import_source(collection={"id": spelling, "title": "x", "language_code": "en", "provenance": {}},
                           source=normalized, records=normalized["records"], mapping=mapping)
    assert repo.list_collections("en", status=None) == [], "no row is created"


@pytest.mark.parametrize("operation", ["publish", "status"])
def test_publish_and_status_on_the_reserved_id_refuse_with_their_own_message_and_create_nothing(repo, operation) -> None:
    with pytest.raises(ValueError, match="General catalogue"):
        if operation == "publish":
            repo.finalize_collection_publication("orena-general-en", admission=VALID)
        else:
            repo.set_collection_status("ORENA-GENERAL-EN", "unpublished", actor="mod")
    assert repo.list_collections("en", status=None) == []


def test_the_resolver_matches_only_the_exact_lower_case_id() -> None:
    assert general_collection_language("orena-general-en") == "en"
    assert general_collection_language("orena-general-zh-hans") == "zh-hans"
    for bad in ("ORENA-GENERAL-EN", " orena-general-en", "orena-general-", "orena-general-en ", "orena-general- en", None, 5, ""):
        assert general_collection_language(bad) is None, bad


def test_a_stored_row_under_the_reserved_id_never_wins_and_never_contributes(repo) -> None:
    make_set(repo, "real", ["alpha"])
    # a row created out of band (SQL), published and perfectly attested
    from sqlalchemy import text

    with repo.engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO vocabulary_collections (id, language_code, title, framework, level, level_range, topic, "
            "catalog_status, origin, provenance, created_at, updated_at) VALUES ('orena-general-en', 'en', 'Spoof', '', '', "
            "'', '', 'published', 'imported', :p, '2026-01-01', '2026-01-01')"), {"p": json.dumps({"admission": VALID})})
    assert general_terms(repo) == ["alpha"]
    assert repo.general_summary("en")["title"] == GENERAL_FALLBACK_TITLE


# ------------------------------------------------------------------------------------------------------ the routes


def _get(path):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_module.app), base_url="http://testserver") as c:
            return await c.get(path)

    return asyncio.run(run())


@pytest.fixture()
def learner(repo, monkeypatch):
    monkeypatch.setattr(app_module, "_persistence_runtime", replace(app_module._persistence_runtime, vocabulary_repository=repo))
    app_module.configure_becoming_library_content(repo)
    return repo


def test_the_list_route_puts_general_last_and_marks_it(learner) -> None:
    make_set(learner, "zzz", ["alpha", "beta"])
    items = _get("/api/vocabulary/library/collections?language_code=en").json()["items"]
    assert [item["id"] for item in items] == ["zzz", "orena-general-en"]
    general = items[-1]
    assert general["system_kind"] == GENERAL_SYSTEM_KIND and general["item_count"] == 2
    assert general["progress"] == {"learned_count": 0, "learning_count": 0, "due_count": 0, "mastered_count": 0}
    assert "provenance" not in general and "attested_by" not in json.dumps(general)


def test_the_list_route_has_no_general_for_a_language_without_qualifying_words(learner) -> None:
    make_set(learner, "pending", ["alpha"], status="pending_review")
    assert _get("/api/vocabulary/library/collections?language_code=en").json()["items"] == []
    assert _get("/api/vocabulary/library/collections?language_code=zh").json()["items"] == []


def test_the_detail_route_pages_general_and_unknown_spellings_are_404_never_500(learner) -> None:
    make_set(learner, "a", [f"w{i:02d}" for i in range(7)])
    page = _get("/api/vocabulary/library/collections/orena-general-en?limit=3&offset=3").json()
    assert page["id"] == "orena-general-en" and len(page["items"]) == 3 and page["pagination"]["total"] == 7
    assert page["system_kind"] == GENERAL_SYSTEM_KIND and "provenance" not in page
    for bad in ("orena-general-xx", "orena-general-", "ORENA-GENERAL-EN", "orena-general-%20en", "orena-general-zh"):
        assert _get(f"/api/vocabulary/library/collections/{bad}").status_code == 404, bad


def test_the_kill_switch_hides_only_general(learner, monkeypatch) -> None:
    make_set(learner, "a", ["alpha"])
    assert policies.default("vocabulary.general_catalogue_enabled") is True, "on by default"
    monkeypatch.setattr(app_module._policies, "value", lambda key, **kw: False if key == "vocabulary.general_catalogue_enabled" else policies.default(key))
    assert [i["id"] for i in _get("/api/vocabulary/library/collections?language_code=en").json()["items"]] == ["a"]
    assert _get("/api/vocabulary/library/collections/orena-general-en").status_code == 404
    assert _get("/api/vocabulary/library/collections/a").status_code == 200
    search = _get("/api/vocabulary/catalogue/search?q=alp&language_code=en").json()["items"]
    assert [item["word"] for item in search] == ["alpha"], "search and the word page are untouched"


def test_progress_counts_only_the_learners_own_saved_words_that_general_contains(learner) -> None:
    from tests.test_vocabulary_library_route import _seed_saved_word

    make_set(learner, "a", ["alpha", "beta"])
    _seed_saved_word("en", "alpha")
    _seed_saved_word("en", "not-in-general")
    general = _get("/api/vocabulary/library/collections?language_code=en").json()["items"][-1]
    assert general["progress"]["learned_count"] == 1
    detail = _get("/api/vocabulary/library/collections/orena-general-en").json()
    assert detail["progress"]["learned_count"] == 1
    assert [c["saved"] for c in detail["items"]] == [True, False]


def test_a_stored_reserved_row_is_not_listed_to_learners(learner) -> None:
    from sqlalchemy import text

    with learner.engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO vocabulary_collections (id, language_code, title, framework, level, level_range, topic, "
            "catalog_status, origin, provenance, created_at, updated_at) VALUES ('orena-general-en', 'en', 'Spoof', '', '', "
            "'', '', 'published', 'imported', :p, '2026-01-01', '2026-01-01')"), {"p": json.dumps({"admission": VALID})})
    assert _get("/api/vocabulary/library/collections?language_code=en").json()["items"] == []
    assert _get("/api/vocabulary/library/collections/orena-general-en").status_code == 404


def test_no_static_collection_id_is_in_the_reserved_space() -> None:
    from writing_coach.vocabulary_library import list_vocabulary_source_collections

    for language in ("en", "zh"):
        assert all(not is_reserved_collection_id(c["id"]) for c in list_vocabulary_source_collections(language))


# ------------------------------------------------------------------------------- import routes, pack, Admin


@pytest.mark.parametrize("spelling", ["orena-general-en", "ORENA-General-en", " orena-general-en", "ｏｒｅｎａ－ｇｅｎｅｒａｌ－ｅｎ"])
def test_the_admin_import_route_refuses_the_reserved_id_before_any_write(learner, spelling) -> None:
    from tests.test_vocabulary_source_routes import _request

    response = _request("POST", "/api/admin/vocabulary/import", data={
        "metadata": json.dumps({"title": "x", "language_code": "en", "collection_id": spelling,
                                "rights_status": "licensed", "completeness": "complete"}),
        "mappings": json.dumps({"w.csv": {"term": "English", "short_meaning": "Vietnamese"}}),
    }, files=[("files", ("w.csv", b"English|Vietnamese\nhello|xin chao\n", "text/csv"))])
    assert response.status_code == 422 and "vocabulary_collection_id_reserved" in response.text
    assert learner.list_collections("en", status=None) == []


@pytest.mark.parametrize("spelling", ["orena-general-en", "ORENA-GENERAL-EN", " orena-general-en"])
def test_the_service_token_import_refuses_the_reserved_id_before_any_write(secured, token_repository, token_on, spelling) -> None:
    data = csv_import_data(collection_id=spelling)
    response = call(secured, "POST", IMPORT, token=TOKEN, files=csv_file(), data=data)
    assert response.status_code == 422, response.text
    assert token_repository.list_collections("en", status=None) == []


def test_the_content_pack_importer_refuses_the_reserved_id(learner) -> None:
    with pytest.raises(ValueError, match="General catalogue"):
        app_module._vocabulary_pack_import(
            {"id": "ORENA-general-en", "title": "x", "language_code": "en", "entries": []}, imported_by="admin", pack_id="p")
    assert learner.list_collections("en", status=None) == []


def test_content_pack_export_and_enumeration_never_see_general(learner) -> None:
    make_set(learner, "a", ["alpha"])
    assert app_module._vocabulary_pack_export("orena-general-en") is None
    ids = [c["id"] for c in learner.list_collections("en")]
    assert ids == ["a"]


def test_admin_publish_and_status_on_the_general_id_are_refused(learner) -> None:
    from tests.test_vocabulary_source_routes import _request

    make_set(learner, "a", ["alpha"])
    publish = _request("POST", "/api/admin/content/vocabulary/orena-general-en/publish",
                       json={"rights_status": "licensed", "completeness": "complete", "attested": True},
                       headers={"origin": "http://testserver"})
    status = _request("POST", "/api/admin/content/vocabulary/orena-general-en/status", json={"status": "unpublished"},
                      headers={"origin": "http://testserver"})
    assert publish.status_code in (404, 422, 503) and status.status_code in (404, 422, 503)
    assert [c["id"] for c in learner.list_collections("en", status=None)] == ["a"]


def test_admin_content_list_is_unchanged_by_the_feature(learner) -> None:
    make_set(learner, "a", ["alpha"])
    from writing_coach.admin_content import vocabulary_record

    assert all(not is_reserved_collection_id(c["id"]) for c in learner.list_collections("en", status=None))
    assert vocabulary_record({"id": "a", "status": "published"})["id"] == "a"
