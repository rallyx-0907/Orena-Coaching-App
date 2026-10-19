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
    build_provenance,
    missing_fields,
    provenance_blockers,
    recognise_license,
)
from writing_coach.reading_source_import import SubmittedInput

LICENCE_URL = "https://creativecommons.org/licenses/by/3.0/"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_published_reading_provenance.py"


def _source(content, *, slug, automation, license_note="", attribution=True, auto_publish=True):
    rights = {"automation_allowed": automation, "can_republish": True, "can_adapt": False,
              "attribution_required": attribution}
    if license_note:
        rights["license_note"] = license_note
    source = content.create_source(
        slug=slug, name="Global Voices (English) RSS - trial", public_name="Global Voices", source_type="manual",
        base_url="", languages=["en", "zh"], rights=rights, created_by="admin")
    content.set_source_state(source["id"], "active", actor="admin")
    if auto_publish:  # #352: these tests exercise a source the owner let publish without a person
        content.set_auto_publish(source["id"], True, actor="admin")
    return source


def test_auto_publish_is_off_for_a_new_source_and_only_an_administrator_turns_it_on(setup):  # noqa: F811
    source = _source(setup["content"], slug="gv-auto", automation=True, auto_publish=False)
    path = f"/api/admin/reading/sources/{source['id']}/auto-publish"
    assert setup["content"].get_source(source["id"])["auto_publish"] == {"enabled": False}
    assert call(setup["admin"], "POST", path, json={"enabled": True}, admin=False).status_code == 403
    assert call(setup["admin"], "POST", path, json={"enabled": True}, origin="https://evil.example").status_code == 403
    assert call(setup["admin"], "POST", path, json={"enabled": "yes"}).status_code == 422
    answer = call(setup["admin"], "POST", path, json={"enabled": True})
    assert answer.status_code == 200 and answer.json()["auto_publish"] == {"enabled": True}
    missing = f"/api/admin/reading/sources/{uuid.uuid4()}/auto-publish"
    assert call(setup["admin"], "POST", missing, json={"enabled": True}).status_code == 404


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
        "publisher": "Global Voices", "via": "", "url": "https://globalvoices.org/2026/10/rain", "author": "Peace News",
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


def test_the_repository_never_refuses_publishing_for_an_incomplete_credit_or_unclear_rights(setup):  # noqa: F811
    # D-189 amends D-105: the admin can always publish; the route asks for the override, not the repository.
    content = setup["content"]
    source = _source(content, slug="gv", automation=False)
    article_id = _submit(setup, source)
    assert provenance_blockers(content.get_article(article_id)["provenance"]) != []
    published = content.set_status(
        article_id, "published", actor="admin", reason="owner confirmed",
        warnings=[{"code": "provenance_missing", "level": "warning"}])
    assert published["status"] == "published"
    event = next(e for e in content.list_review_events(article_id) if e["action"] == "published")
    assert event["changes"]["published_over_warnings"] is True and event["reason"] == "owner confirmed"
    # Even denied or unanswered republish rights do not stop the repository.
    other = _submit(setup, _source(content, slug="gv2", automation=False), title="Other", body=ARTICLE + "More. ")
    content.set_rights(other, {"can_republish": False}, actor="admin")
    assert content.set_status(other, "published", actor="admin")["status"] == "published"


def _publish_body(**extra):
    return {"status": "published", **extra}


def test_the_admin_route_asks_for_an_override_over_an_incomplete_credit(setup):  # noqa: F811
    content = setup["content"]
    source = _source(content, slug="gv", automation=False)
    article_id = _submit(setup, source)
    url = f"/api/admin/reading/articles/{article_id}/status"
    refused = call(setup["admin"], "POST", url, json=_publish_body())
    assert refused.status_code == 409
    context = refused.json()["detail"]["context"]
    assert {"code": "provenance_missing", "question": "attribution_required", "field": "license",
            "level": "warning"} in context["blockers"]
    assert context["override_field"] == "acknowledge_warnings"
    assert content.get_article(article_id)["status"] != "published"
    no_reason = call(setup["admin"], "POST", url, json=_publish_body(acknowledge_warnings=True))
    assert no_reason.status_code == 422
    assert no_reason.json()["detail"]["category"] == "reading_reason_required"
    assert content.get_article(article_id)["status"] != "published"
    allowed = call(setup["admin"], "POST", url, json=_publish_body(acknowledge_warnings=True, reason="licence on file"))
    assert allowed.status_code == 200 and allowed.json()["status"] == "published"
    assert any(w["code"] == "provenance_missing" for w in allowed.json()["publication_warnings"])
    event = next(e for e in content.list_review_events(article_id) if e["action"] == "published")
    assert event["reason"] == "licence on file" and event["actor"]
    assert any(w["code"] == "provenance_missing" for w in event["changes"]["warnings"])
    assert any(r["action"] == "admin.reading_article_published" for r in setup["audit"])


def test_recording_the_credit_publishes_without_an_override(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=False))
    call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/rights", json={"license_note": "CC BY 3.0"})
    allowed = call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status", json=_publish_body())
    assert allowed.status_code == 200 and allowed.json()["publication_warnings"] == []


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
        "publisher", "via", "url", "author", "license", "attribution_required", "text"}
    assert not FORBIDDEN_KEYS & set(_keys(listed)) and not FORBIDDEN_KEYS & set(_keys(detail["provenance"]))
    assert "reviewer@example.com" not in json.dumps(listed) + json.dumps(detail)


def test_an_unanswered_attribution_question_still_publishes_by_an_administrator(setup):  # noqa: F811
    # The repository never refuses (D-189 amends D-105); the admin route asks for the override (below).
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


def test_republishing_after_the_credit_was_removed_asks_for_the_override_again(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=False, license_note="CC BY 3.0"))
    content.set_status(article_id, "published", actor="admin")
    content.set_status(article_id, "unpublished", actor="admin")
    content.set_rights(article_id, {"license_note": None}, actor="admin")
    url = f"/api/admin/reading/articles/{article_id}/status"
    assert call(setup["admin"], "POST", url, json=_publish_body()).status_code == 409
    assert content.get_article(article_id)["status"] == "unpublished"
    again = call(setup["admin"], "POST", url, json=_publish_body(acknowledge_warnings=True, reason="kept"))
    assert again.status_code == 200


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
    assert {"code": "adaptation_not_cleared", "question": "can_adapt", "level": "warning"} in blockers
    assert {"code": "provenance_missing", "question": "attribution_required", "field": "license",
            "level": "warning"} in blockers


def _manual_article(setup, rights):  # noqa: F811
    content = setup["content"]
    snapshot = content.record_source_item(
        source_id=content.built_in_source_id("manual"), source_native_id="", canonical_url="", title="T",
        author="", published_at=None, language="en", body=ARTICLE, content_hash=uuid.uuid4().hex * 2, metadata={},
        rights=rights)
    return content.create_article(
        source_item_id=snapshot["id"], title="T", body=ARTICLE, excerpt="", language="en", topic="",
        estimated_level="B1", estimated_confidence=0.5, word_count=60, reading_time_seconds=60,
        analysis={}, targets=[])["id"]


@pytest.mark.parametrize("rights,code", [
    ({"can_republish": True}, "attribution_unknown"),
    ({"can_republish": False, "attribution_required": False}, "rights_not_cleared"),
    ({"attribution_required": False}, "rights_unknown"),
])
def test_unclear_rights_or_attribution_need_the_explicit_override_and_reason(setup, rights, code):  # noqa: F811
    article_id = _manual_article(setup, rights)
    url = f"/api/admin/reading/articles/{article_id}/status"
    refused = call(setup["admin"], "POST", url, json=_publish_body())
    assert refused.status_code == 409
    assert code in {item["code"] for item in refused.json()["detail"]["context"]["blockers"]}
    assert setup["content"].get_article(article_id)["status"] != "published"
    assert call(setup["admin"], "POST", url, json=_publish_body(acknowledge_warnings=True, reason="  ")).status_code == 422
    done = call(setup["admin"], "POST", url, json=_publish_body(acknowledge_warnings=True, reason="reviewed by owner"))
    assert done.status_code == 200 and code in {w["code"] for w in done.json()["publication_warnings"]}
    event = next(e for e in setup["content"].list_review_events(article_id) if e["action"] == "published")
    assert event["reason"] == "reviewed by owner"
    assert code in {w["code"] for w in event["changes"]["warnings"]}


def test_a_cleared_internal_text_publishes_without_an_override(setup):  # noqa: F811
    article_id = _manual_article(setup, {"can_republish": True, "attribution_required": False})
    done = call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status", json=_publish_body())
    assert done.status_code == 200 and done.json()["publication_warnings"] == []


def test_automatic_admission_still_refuses_unclear_attribution_and_rights():
    from writing_coach.reading_admission import automatic_admission

    source = {"state": "active", "languages": ["en"], "name": "S", "base_url": "",
              "rights": {"automation_allowed": True, "can_republish": True}}
    snapshot = {"rights": {"can_republish": True}, "body": "b", "language": "en", "canonical_url": ""}
    reasons = automatic_admission(source=source, snapshot=snapshot, language="en", body="b", analysis={},
                                  targets=[], min_targets=1, max_targets=2)["reasons"]
    assert "attribution_unknown" in reasons
    snapshot["rights"] = {"can_republish": False, "attribution_required": False}
    reasons = automatic_admission(source=source, snapshot=snapshot, language="en", body="b", analysis={},
                                  targets=[], min_targets=1, max_targets=2)["reasons"]
    assert "rights_not_cleared" in reasons
    snapshot["rights"] = {"can_republish": True, "attribution_required": True}
    reasons = automatic_admission(source=source, snapshot=snapshot, language="en", body="b", analysis={},
                                  targets=[], min_targets=1, max_targets=2)["reasons"]
    assert "attribution_missing" in reasons


def test_the_checker_reports_whether_an_incomplete_credit_was_published_over_a_recorded_override(setup, capsys):  # noqa: F811
    content = setup["content"]
    overridden = _submit(setup, _source(content, slug="gv-o", automation=False), title="Overridden")
    call(setup["admin"], "POST", f"/api/admin/reading/articles/{overridden}/status",
         json=_publish_body(acknowledge_warnings=True, reason="licence on file"))
    legacy = _submit(setup, _source(content, slug="gv-l", automation=False), title="Legacy",
                     body=ARTICLE + "Another line. ")
    with content.engine.begin() as connection:
        connection.execute(update(ReadingArticle).where(ReadingArticle.id == uuid.UUID(legacy))
                           .values(status=LEARNER_VISIBLE_STATUS))
    found = {item["id"]: item for item in _load_checker().find_published_without_provenance(content.engine)}
    assert found[overridden]["overridden"] is True and found[legacy]["overridden"] is False
    # Only an incomplete credit with no recorded override is a violation.
    with content.engine.begin() as connection:
        connection.execute(update(ReadingArticle).where(ReadingArticle.id == uuid.UUID(legacy))
                           .values(status="unpublished"))
    only_overridden = _load_checker().find_published_without_provenance(content.engine)
    assert [item["overridden"] for item in only_overridden] == [True]
