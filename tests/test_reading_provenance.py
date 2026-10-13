"""D-189: a published Reading text carries the credit its source terms require.

What these hold: the learner list and detail return a provenance object derived
from the stored source record and the effective rights; publishing is refused on
every path (the administrator's route, the repository transition and the
deterministic automatic admission) while required attribution is incomplete and
allowed once it is complete; and the read-only checker lists published articles
that fall short without changing anything.
"""
from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import update

from tests.test_reading_content_engine import ARTICLE, ZH_ARTICLE
from tests.test_reading_engine_routes import call, setup  # noqa: F401 - the route fixture
from writing_coach.persistence.models import ReadingArticle
from writing_coach.persistence.reading_content_repository import LEARNER_VISIBLE_STATUS
from writing_coach.reading_provenance import (
    ProvenanceRefused,
    build_provenance,
    missing_fields,
    provenance_blockers,
    recognise_license,
)
from writing_coach.reading_source_import import SubmittedInput

LICENCE_URL = "https://creativecommons.org/licenses/by/3.0/"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_published_reading_provenance.py"


def _source(content, *, slug, automation, license_note="", attribution=True):
    rights = {"automation_allowed": automation, "can_republish": True, "can_adapt": False,
              "attribution_required": attribution}
    if license_note:
        rights["license_note"] = license_note
    source = content.create_source(
        slug=slug, name="Global Voices", source_type="manual", base_url="",
        languages=["en", "zh"], rights=rights, created_by="admin")
    content.set_source_state(source["id"], "active", actor="admin")
    return source


def _submit(parts, source, *, body=ARTICLE, language="en", url="https://globalvoices.org/2026/10/rain",
            author="Peace News", title="Rain returns"):
    parts["engine"].submit(SubmittedInput(
        kind="text", text=body, title=title, author=author, language=language, url=url,
        source_id=source["id"]), actor="admin")
    return parts["engine"].process(parts["jobs"].claim("worker"))["article_id"]


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_published_reading_provenance", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# -- the pure derivation ---------------------------------------------------------------


def test_only_a_recognised_licence_is_named_and_the_note_is_never_passed_on():
    cc = "https://creativecommons.org/licenses/by/3.0/"
    assert recognise_license(f"CC BY 3.0 - {cc}") == {"name": "CC BY 3.0", "url": cc, "recorded": True}
    # Without an address in the note, the Creative Commons one is derived.
    assert recognise_license("CC BY-SA 4.0.") == {
        "name": "CC BY-SA 4.0", "url": "https://creativecommons.org/licenses/by-sa/4.0/", "recorded": True}
    assert recognise_license("cc0")["name"] == "CC0 1.0"
    assert recognise_license("Public Domain") == {"name": "Public domain", "url": "", "recorded": True}
    # A note that is only an address names nothing but keeps the (Creative Commons) address.
    assert recognise_license(cc) == {"name": "", "url": cc, "recorded": True}
    # An explicit address is used, but only a Creative Commons one.
    assert recognise_license("CC BY 3.0", "https://creativecommons.org/licenses/by/2.0/")["url"].endswith("/by/2.0/")
    assert recognise_license("CC BY 3.0", "https://evil.example/x")["url"] == "https://creativecommons.org/licenses/by/3.0/"
    assert recognise_license("", "https://creativecommons.org/licenses/by/2.0/")["recorded"] is True
    # Free text that names no recognised licence is recorded, never exposed.
    assert recognise_license("internal: ask Bob before reuse") == {"name": "", "url": "", "recorded": True}
    assert recognise_license("") == {"name": "", "url": "", "recorded": False}


def test_provenance_names_the_publisher_the_original_the_author_and_the_licence():
    credit = build_provenance(
        publisher="Global Voices", url="https://globalvoices.org/a", author="Peace News",
        rights={"attribution_required": True, "license_note": "CC BY 3.0"})
    assert credit["publisher"] == "Global Voices"
    assert credit["url"] == "https://globalvoices.org/a"
    assert credit["author"] == "Peace News"
    assert credit["license"] == {
        "name": "CC BY 3.0", "url": "https://creativecommons.org/licenses/by/3.0/", "recorded": True}
    assert credit["attribution_required"] == "required"
    assert credit["text"] == "Originally published by Global Voices (by Peace News), CC BY 3.0."
    assert provenance_blockers(credit) == []


@pytest.mark.parametrize("rights,expected", [
    ({"attribution_required": True}, ["license"]),
    ({"attribution_required": True, "license_note": "CC BY 3.0"}, []),
    ({"attribution_required": False}, []),
    ({}, []),
])
def test_only_required_attribution_can_be_missing(rights, expected):
    credit = build_provenance(publisher="Global Voices", url="https://x.example/a", author="", rights=rights)
    assert missing_fields(credit) == expected


def test_an_incomplete_credit_names_each_missing_part():
    credit = build_provenance(publisher="", url="", author="A", rights={"attribution_required": True})
    assert [item["field"] for item in provenance_blockers(credit)] == ["publisher", "url", "license"]


# -- the learner payloads (EN and ZH) --------------------------------------------------------


@pytest.mark.parametrize("language,body", [("en", ARTICLE), ("zh", ZH_ARTICLE)])
def test_the_learner_list_and_detail_carry_the_provenance(setup, language, body):  # noqa: F811
    content = setup["content"]
    source = _source(content, slug=f"gv-{language}", automation=True, license_note=f"CC BY 3.0 {LICENCE_URL}")
    article_id = _submit(setup, source, body=body, language=language)
    assert content.get_article(article_id)["status"] == "published"
    expected = {
        "publisher": "Global Voices", "url": "https://globalvoices.org/2026/10/rain", "author": "Peace News",
        "license": {"name": "CC BY 3.0", "url": LICENCE_URL, "recorded": True}, "attribution_required": "required",
        "text": "Originally published by Global Voices (by Peace News), CC BY 3.0.",
    }
    listed = call(setup["learner"], "GET", f"/api/reading/articles?language={language}", admin=False).json()
    assert listed["items"][0]["provenance"] == expected
    detail = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).json()
    assert detail["provenance"] == expected


def test_a_recorded_licence_answer_reaches_the_learner_and_moves_the_cache_revision(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content, slug="gv", automation=False, attribution=False)
    article_id = _submit(setup, source)
    content.set_status(article_id, "published", actor="admin")
    before = content.get_published_article(article_id)
    assert before["provenance"]["license"] == {"name": "", "url": "", "recorded": False}
    content.set_rights(article_id, {"license_note": "CC BY 3.0"}, actor="admin")
    after = content.get_published_article(article_id)
    assert after["provenance"]["license"]["name"] == "CC BY 3.0"
    assert after["content_revision"] > before["content_revision"]


# -- the gate on every publish path ------------------------------------------------------------


def test_the_repository_refuses_publishing_without_the_required_credit_and_allows_it_with(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content, slug="gv", automation=False)
    article_id = _submit(setup, source)
    with pytest.raises(ProvenanceRefused) as refused:
        content.set_status(article_id, "published", actor="admin")
    assert [item["field"] for item in refused.value.blockers] == ["license"]
    assert content.get_article(article_id)["status"] != "published"
    content.set_rights(article_id, {"license_note": "CC BY 3.0"}, actor="admin")
    assert content.set_status(article_id, "published", actor="admin")["status"] == "published"


def test_the_admin_route_refuses_publishing_without_the_required_credit_and_allows_it_with(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content, slug="gv", automation=False)
    article_id = _submit(setup, source)
    refused = call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
                   json={"status": "published"})
    assert refused.status_code == 409
    blockers = refused.json()["detail"]["context"]["blockers"]
    assert {"code": "provenance_missing", "question": "attribution_required", "field": "license"} in blockers
    assert content.get_article(article_id)["status"] != "published"
    answered = call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/rights",
                    json={"license_note": "CC BY 3.0"})
    assert answered.status_code == 200
    allowed = call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
                   json={"status": "published"})
    assert allowed.status_code == 200 and allowed.json()["status"] == "published"


def test_a_source_that_does_not_require_attribution_is_not_held_by_the_credit(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content, slug="owned", automation=False, attribution=False)
    article_id = _submit(setup, source, url="")
    assert content.set_status(article_id, "published", actor="admin")["status"] == "published"


def test_automatic_admission_holds_an_article_whose_credit_is_incomplete(setup):  # noqa: F811
    content = setup["content"]
    incomplete = _source(content, slug="gv-nolicence", automation=True)
    held = _submit(setup, incomplete)
    article = content.get_article(held)
    assert article["status"] == "needs_review"
    assert "attribution_missing" in article["analysis"]["admission"]["reasons"]
    complete = _source(content, slug="gv-licence", automation=True, license_note="CC BY 3.0")
    admitted = _submit(setup, complete, body=ARTICLE + "A second paragraph follows the first. ", title="Rain again")
    assert content.get_article(admitted)["status"] == "published"


# -- the read-only checker ------------------------------------------------------------------------


def test_the_checker_lists_published_articles_missing_required_attribution_and_changes_nothing(setup, tmp_path, capsys):  # noqa: F811
    content = setup["content"]
    good = _submit(setup, _source(content, slug="gv-ok", automation=True, license_note="CC BY 3.0"))
    legacy = _submit(setup, _source(content, slug="gv-legacy", automation=False), title="Legacy",
                     body=ARTICLE + "Another line. ")
    # A row published before the gate existed: the status is set directly.
    with content.engine.begin() as connection:
        connection.execute(update(ReadingArticle).where(ReadingArticle.id == uuid.UUID(legacy))
                           .values(status=LEARNER_VISIBLE_STATUS))
    checker = _load_checker()
    found = checker.find_published_without_provenance(content.engine)
    assert [item["id"] for item in found] == [legacy]
    assert found[0]["missing"] == ["license"]
    assert good not in {item["id"] for item in found}
    assert content.get_article(legacy)["status"] == "published"
    assert checker.main(["--url", ""]) == 2
    capsys.readouterr()

# -- review conditions (P1-2 and the negative cases) ------------------------------------------------

INTERNAL_NOTE = "INTERNAL-ONLY: legal said ask Bob before reuse, contract ref 4471 " + "x" * 1500
FORBIDDEN_KEYS = {"rights_effective", "rights", "rights_state", "rights_review", "actor", "notes", "license_note",
                  "analysis", "source", "automation", "admin"}


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


def test_an_internal_licence_note_never_reaches_a_learner_payload(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content, slug="gv", automation=False, license_note=INTERNAL_NOTE)
    article_id = _submit(setup, source)
    # The administrator recorded a licence statement, so the credit is complete, but none of its words leak.
    assert content.set_status(article_id, "published", actor="admin")["status"] == "published"
    listed = call(setup["learner"], "GET", "/api/reading/articles?language=en", admin=False)
    detail = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False)
    for response in (listed, detail):
        assert "INTERNAL-ONLY" not in response.text and "4471" not in response.text and "xxxx" not in response.text
        assert len(response.text) < 20000
    credit = detail.json()["provenance"]
    assert credit["license"] == {"name": "", "url": "", "recorded": True}
    assert credit["text"] == "Originally published by Global Voices (by Peace News)."
    assert len(credit["text"]) < 300


def test_the_learner_payload_carries_no_rights_or_review_keys(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=True, license_note="CC BY 3.0"))
    content.set_rights(article_id, {"license_note": "CC BY 3.0"}, actor="reviewer@example.com", reason="checked")
    listed = call(setup["learner"], "GET", "/api/reading/articles?language=en", admin=False).json()
    detail = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).json()
    assert set(listed["items"][0]["provenance"]) == {
        "publisher", "url", "author", "license", "attribution_required", "text"}
    assert not FORBIDDEN_KEYS & set(_keys(listed)) and not FORBIDDEN_KEYS & set(_keys(detail["provenance"]))
    assert "reviewer@example.com" not in json.dumps(listed) + json.dumps(detail)


def test_an_unanswered_attribution_question_still_publishes_by_an_administrator(setup):  # noqa: F811
    # The current policy, pinned and not decided here: `unknown` is advice (P1-1 is a human decision).
    content = setup["content"]
    snapshot = content.record_source_item(
        source_id=content.built_in_source_id("manual"), source_native_id="", canonical_url="", title="T",
        author="", published_at=None, language="en", body=ARTICLE, content_hash="e" * 64, metadata={},
        rights={"can_republish": True})
    article_id = content.create_article(
        source_item_id=snapshot["id"], title="T", body=ARTICLE, excerpt="", language="en", topic="",
        estimated_level="B1", estimated_confidence=0.5, word_count=60, reading_time_seconds=60,
        analysis={}, targets=[])["id"]
    assert content.get_article(article_id)["provenance"]["attribution_required"] == "unknown"
    assert content.set_status(article_id, "published", actor="admin")["status"] == "published"


def test_a_note_that_is_only_an_address_and_a_later_answer_both_satisfy_the_gate(setup):  # noqa: F811
    content = setup["content"]
    first = _submit(setup, _source(content, slug="a", automation=False, license_note=LICENCE_URL))
    assert content.get_article(first)["provenance"]["license"] == {"name": "", "url": LICENCE_URL, "recorded": True}
    assert content.set_status(first, "published", actor="admin")["status"] == "published"
    second = _submit(setup, _source(content, slug="b", automation=False), title="Second", body=ARTICLE + "More. ")
    content.set_rights(second, {"license_note": "CC BY 4.0"}, actor="admin")
    assert content.get_article(second)["provenance"]["license"]["url"].endswith("/by/4.0/")


def test_republishing_is_refused_when_the_credit_was_removed_in_the_meantime(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=False, license_note="CC BY 3.0"))
    content.set_status(article_id, "published", actor="admin")
    content.set_status(article_id, "unpublished", actor="admin")
    content.set_rights(article_id, {"license_note": None}, actor="admin")
    with pytest.raises(ProvenanceRefused):
        content.set_status(article_id, "published", actor="admin")
    assert content.get_article(article_id)["status"] == "unpublished"


def test_a_rights_answer_on_an_unpublished_article_does_not_move_the_cache_revision(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=False, license_note="CC BY 3.0"))
    before = content.get_article(article_id)["content_revision"]
    content.set_rights(article_id, {"license_note": "CC BY 4.0"}, actor="admin")
    assert content.get_article(article_id)["content_revision"] == before


def test_a_text_that_needs_both_adaptation_and_a_credit_returns_both_blockers(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=False))
    with content.engine.begin() as connection:
        connection.execute(update(ReadingArticle).where(ReadingArticle.id == uuid.UUID(article_id))
                           .values(is_adapted=True))
    refused = call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
                   json={"status": "published"})
    assert refused.status_code == 409
    blockers = refused.json()["detail"]["context"]["blockers"]
    assert {"code": "adaptation_not_cleared", "question": "can_adapt"} in blockers
    assert {"code": "provenance_missing", "question": "attribution_required", "field": "license"} in blockers
