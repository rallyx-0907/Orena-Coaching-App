"""D-250 (amends D-190; Hermes for the owner, 2026-10-21, PRE-203): a Reading article is published only when its rights
are clear. The D-190 override (`acknowledge_warnings` and a reason) is gone - in the route and in the repository, so a
script that publishes directly is stopped too. Nothing already published is taken down; a read-only checker lists it."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest

from tests.test_reading_engine_routes import call, setup  # noqa: F401 - the route fixture
from tests.test_reading_content_engine import ARTICLE
from tests.test_reading_provenance import _source, _submit
from writing_coach.reading_rights_gate import RightsRefused, rights_blockers

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_published_reading_rights_gate.py"


def _credited(content, article_id):
    """Record the licence on the article itself, as its review page does: the credit is then complete."""
    content.set_rights(article_id, {"license_note": "CC BY 3.0"}, actor="admin")
    return article_id


def _status(setup, article_id, **body):  # noqa: F811
    return call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
                json={"status": "published", **body})  # fmt: skip


def test_unclear_rights_are_refused_even_with_the_old_override(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=False))  # credit incomplete
    refused = _status(setup, article_id, acknowledge_warnings=True, reason="owner confirmed by email")
    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert detail["category"] == "reading_rights_not_cleared"
    assert "provenance_missing" in {item["code"] for item in detail["context"]["blockers"]}
    assert detail["context"]["override_fields"] == [] and "override_field" not in detail["context"]
    assert content.get_article(article_id)["status"] != "published"


def test_the_repository_refuses_a_direct_publish_too(setup):  # noqa: F811
    content = setup["content"]
    article_id = _submit(setup, _source(content, slug="gv", automation=False))
    with pytest.raises(RightsRefused) as refused:
        content.set_status(article_id, "published", actor="script")
    assert "provenance_missing" in {item["code"] for item in refused.value.blockers}
    assert content.get_article(article_id)["status"] != "published"


def test_denied_or_unanswered_republish_rights_refuse(setup):  # noqa: F811
    content = setup["content"]
    article_id = _credited(content, _submit(setup, _source(content, slug="gv", automation=False)))
    content.set_rights(article_id, {"can_republish": False}, actor="admin")
    with pytest.raises(RightsRefused) as refused:
        content.set_status(article_id, "published", actor="admin")
    assert [item["code"] for item in refused.value.blockers] == ["rights_not_cleared"]


def test_clear_rights_publish_with_no_reason_and_no_warnings_recorded(setup):  # noqa: F811
    content = setup["content"]
    article_id = _credited(content, _submit(setup, _source(content, slug="gv", automation=False)))
    assert rights_blockers(content.get_article(article_id)) == []
    published = _status(setup, article_id)
    assert published.status_code == 200 and published.json()["publication_warnings"] == []
    event = next(e for e in content.list_review_events(article_id) if e["action"] == "published")
    assert "published_over_warnings" not in event["changes"] and "warnings" not in event["changes"]


def test_an_unanswered_attribution_question_refuses(setup):  # noqa: F811
    article = {"source": {"publication_rights": {"basis": "snapshot", "state": {
        "can_republish": "allowed", "attribution_required": "unknown"}}}, "provenance": {}}
    assert [item["code"] for item in rights_blockers(article)] == ["attribution_unknown"]


def test_an_adapted_text_needs_the_adapt_right():
    state = {"can_republish": "allowed", "attribution_required": "denied"}
    article = {"is_adapted": True, "source": {"publication_rights": {"basis": "snapshot", "state": state}},
               "provenance": {}}
    assert [item["code"] for item in rights_blockers(article)] == ["adaptation_unknown"]
    state["can_adapt"] = "denied"
    assert [item["code"] for item in rights_blockers(article)] == ["adaptation_not_cleared"]
    state["can_adapt"] = "allowed"
    assert rights_blockers(article) == []


def _load_checker():
    spec = importlib.util.spec_from_file_location("check_published_reading_rights_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_checker_lists_published_articles_the_gate_would_refuse_and_changes_nothing(setup):  # noqa: F811
    from sqlalchemy import update

    from writing_coach.persistence.models import ReadingArticle
    from writing_coach.persistence.reading_content_repository import LEARNER_VISIBLE_STATUS

    content = setup["content"]
    clear = _credited(content, _submit(setup, _source(content, slug="clear", automation=False)))
    content.set_status(clear, "published", actor="admin")
    old = _submit(setup, _source(content, slug="old", automation=False), title="Old", body=ARTICLE + "More. ",
                  url="https://globalvoices.org/2026/10/old")
    # published before D-250 (as D-190 allowed): put straight into the published state
    with content.engine.begin() as connection:
        connection.execute(update(ReadingArticle).where(ReadingArticle.id == uuid.UUID(old))
                           .values(status=LEARNER_VISIBLE_STATUS))  # fmt: skip
    found = _load_checker().find_published_rights_violations(content.engine)
    assert [item["id"] for item in found] == [old]
    assert "provenance_missing" in found[0]["blockers"] and found[0]["overridden"] is False
    assert content.get_article(old)["status"] == LEARNER_VISIBLE_STATUS  # listed, never taken down
