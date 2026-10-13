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
    split_license,
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


def test_a_licence_note_is_split_into_a_name_and_an_address():
    assert split_license(f"CC BY 3.0 - {LICENCE_URL}") == {"name": "CC BY 3.0", "url": LICENCE_URL}
    assert split_license("CC BY 3.0") == {"name": "CC BY 3.0", "url": ""}
    assert split_license("", LICENCE_URL) == {"name": "", "url": LICENCE_URL}


def test_provenance_names_the_publisher_the_original_the_author_and_the_licence():
    credit = build_provenance(
        publisher="Global Voices", url="https://globalvoices.org/a", author="Peace News",
        rights={"attribution_required": True, "license_note": "CC BY 3.0"})
    assert credit["publisher"] == "Global Voices"
    assert credit["url"] == "https://globalvoices.org/a"
    assert credit["author"] == "Peace News"
    assert credit["license"] == {"name": "CC BY 3.0", "url": ""}
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
        "license": {"name": "CC BY 3.0", "url": LICENCE_URL}, "attribution_required": "required",
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
    assert before["provenance"]["license"] == {"name": "", "url": ""}
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
