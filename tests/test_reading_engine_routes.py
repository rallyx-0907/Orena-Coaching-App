"""The two HTTP boundaries of the Reading engine, on a real SQLite schema.

Admin and learner are deliberately separate apps here, because they are
separate contracts: the admin side submits, reviews and publishes; the learner
side reads published articles and nothing else. What these tests hold is the
seam between them - that no admin route publishes as a side effect, that no
learner route can reach a candidate, and that a list never carries what only a
detail read should.
"""
from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from writing_coach import reading_admin_api as admin_api
from writing_coach import reading_articles_api as learner_api
from writing_coach.persistence.models import Base
from writing_coach.persistence.reading_content_repository import ReadingContentRepository
from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_content_engine import ReadingContentEngine

ADMIN = {"google_sub": "sub-admin", "email": "admin@example.com", "role": "admin"}
ARTICLE = (
    "The river rose overnight and the fields were flooded by morning. "
    "Farmers moved their animals to higher ground before the water reached the road. "
    "The council opened the hall to families whose homes were cut off by the water. "
    "By Tuesday the level had fallen and volunteers began to clear the worst of the mud. "
    "Nobody was hurt, but several families will not return home before the end of the month. "
)


def guard(request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "Platform administrator access required")
    return ADMIN


@pytest.fixture()
def setup():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    content = ReadingContentRepository(engine)
    content.ensure_built_in_sources()
    jobs = ReadingJobRepository(engine)
    engine_service = ReadingContentEngine(content=content, jobs=jobs)
    recorded: list[dict] = []

    def audit(action, *, actor_key, entity_type="", entity_id="", payload=None):
        recorded.append({"action": action, "actor": actor_key, "entity_id": entity_id})

    admin_api.configure_reading_admin(
        admin_guard=guard, content=content, jobs=jobs, engine=engine_service, audit=audit
    )
    learner_api.configure_reading_articles(content, language_supported=lambda code: code in {"en", "zh"})
    admin_app, learner_app = FastAPI(), FastAPI()
    admin_app.include_router(admin_api.router)
    learner_app.include_router(learner_api.router)
    yield {
        "admin": admin_app, "learner": learner_app, "content": content, "jobs": jobs,
        "engine": engine_service, "audit": recorded,
    }
    admin_api.configure_reading_admin(admin_guard=None)
    learner_api.configure_reading_articles(None)


def call(app, method, path, *, admin=True, origin="http://testserver", **kwargs):
    headers = {"x-test-admin": "1"} if admin else {}
    if origin and method.upper() != "GET":
        headers["origin"] = origin
    headers.update(kwargs.pop("headers", None) or {})

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run())


def _publish_one(setup, *, language="en", topic="environment"):
    """Submit, process and publish one article through the real routes."""
    response = call(setup["admin"], "POST", "/api/admin/reading/jobs",
                    data={"kind": "text", "text": ARTICLE, "title": "Rain returns", "language": language})
    assert response.status_code == 202
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    article_id = outcome["article_id"]
    if topic:
        call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}",
             json={"topic": topic})
    call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
         json={"status": "published"})
    return article_id


ADMIN_READS = ["/sources", "/queue", "/jobs", "/operations"]


# ---- authorization ----------------------------------------------------------

@pytest.mark.parametrize("path", ADMIN_READS)
def test_every_admin_read_requires_an_administrator(setup, path):
    assert call(setup["admin"], "GET", f"/api/admin/reading{path}", admin=False).status_code == 403
    assert call(setup["admin"], "GET", f"/api/admin/reading{path}").status_code == 200


def test_a_change_from_another_site_is_refused_even_with_the_session(setup):
    refused = call(setup["admin"], "POST", "/api/admin/reading/jobs",
                   origin="https://evil.example.com", data={"kind": "text", "text": ARTICLE})
    assert refused.status_code == 403
    assert refused.json()["detail"]["category"] == "admin_origin_mismatch"


def test_a_change_with_no_origin_at_all_is_refused(setup):
    refused = call(setup["admin"], "POST", "/api/admin/reading/jobs", origin="",
                   data={"kind": "text", "text": ARTICLE})
    assert refused.status_code == 403
    assert refused.json()["detail"]["category"] == "admin_origin_required"


def test_the_learner_routes_need_no_administrator(setup):
    assert call(setup["learner"], "GET", "/api/reading/articles?language=en", admin=False).status_code == 200


# ---- submission -------------------------------------------------------------

def test_submitting_returns_202_and_a_job_rather_than_an_article(setup):
    response = call(setup["admin"], "POST", "/api/admin/reading/jobs",
                    data={"kind": "text", "text": ARTICLE, "title": "Rain returns"})
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued" and body["duplicate"] is False
    assert call(setup["admin"], "GET", "/api/admin/reading/queue").json()["items"] == []


def test_a_double_submitted_form_reports_the_first_job(setup):
    first = call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE}).json()
    second = call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE}).json()
    assert second["duplicate"] is True and second["id"] == first["id"]


def test_an_unsupported_input_is_refused_with_a_reason(setup):
    response = call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "telepathy"})
    assert response.status_code == 422
    assert response.json()["detail"]["category"] == "unsupported_input"


def test_the_job_view_does_not_hand_back_the_submitted_payload(setup):
    job = call(setup["admin"], "POST", "/api/admin/reading/jobs",
               data={"kind": "text", "text": ARTICLE}).json()
    detail = call(setup["admin"], "GET", f"/api/admin/reading/jobs/{job['id']}").json()
    assert "input_json" not in detail
    assert detail["status"] == "queued"


def test_every_submission_is_audited(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    assert any(row["action"] == "admin.reading_ingestion_submitted" for row in setup["audit"])


# ---- review and publication --------------------------------------------------

def test_the_queue_is_metadata_and_the_preview_is_where_the_body_is(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    row = call(setup["admin"], "GET", "/api/admin/reading/queue").json()["items"][0]
    assert "body" not in row and "analysis" not in row
    preview = call(setup["admin"], "GET", f"/api/admin/reading/articles/{outcome['article_id']}").json()
    assert preview["body"].startswith("The river rose")
    assert preview["source"]["body"].startswith("The river rose")
    assert preview["events"][0]["action"] == "created"


def test_publishing_is_its_own_act_and_is_audited(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    assert call(setup["learner"], "GET", "/api/reading/articles?language=en").json()["items"] == []
    response = call(setup["admin"], "POST", f"/api/admin/reading/articles/{outcome['article_id']}/status",
                    json={"status": "published"})
    assert response.status_code == 200 and response.json()["published_at"]
    assert any(row["action"] == "admin.reading_article_published" for row in setup["audit"])


def test_a_rejection_must_say_why(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    refused = call(setup["admin"], "POST", f"/api/admin/reading/articles/{outcome['article_id']}/status",
                   json={"status": "rejected", "reason": "  "})
    assert refused.status_code == 422
    assert refused.json()["detail"]["category"] == "reading_reason_required"


def test_an_invalid_status_is_refused_rather_than_stored(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    refused = call(setup["admin"], "POST", f"/api/admin/reading/articles/{outcome['article_id']}/status",
                   json={"status": "deleted"})
    assert refused.status_code == 422


def test_a_level_override_keeps_the_machine_estimate_and_is_audited(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    before = call(setup["admin"], "GET", f"/api/admin/reading/articles/{outcome['article_id']}").json()
    updated = call(setup["admin"], "POST", f"/api/admin/reading/articles/{outcome['article_id']}",
                   json={"reviewed_level": "C1"}).json()
    assert updated["estimated_level"] == before["estimated_level"]
    assert updated["reviewed_level"] == "C1" and updated["effective_level"] == "C1"
    assert any(row["action"] == "admin.reading_level_override" for row in setup["audit"])


def test_clearing_the_override_returns_to_the_machine_estimate(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    path = f"/api/admin/reading/articles/{outcome['article_id']}"
    call(setup["admin"], "POST", path, json={"reviewed_level": "C1"})
    cleared = call(setup["admin"], "POST", path, json={"reviewed_level": ""}).json()
    assert cleared["reviewed_level"] is None
    assert cleared["effective_level"] == cleared["estimated_level"]


def test_a_target_decision_is_recorded_as_the_admins(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    preview = call(setup["admin"], "GET", f"/api/admin/reading/articles/{outcome['article_id']}").json()
    target = preview["targets"][0]
    decided = call(setup["admin"], "POST",
                   f"/api/admin/reading/articles/{outcome['article_id']}/targets/{target['id']}",
                   json={"approved": True}).json()
    assert decided["admin_approved"] is True and decided["machine_suggested"] is True


def test_an_unknown_article_is_a_404_not_a_500(setup):
    missing = call(setup["admin"], "GET", f"/api/admin/reading/articles/{uuid.uuid4()}")
    assert missing.status_code == 404


# ---- sources ----------------------------------------------------------------

def test_a_new_source_cannot_start_polling(setup):
    created = call(setup["admin"], "POST", "/api/admin/reading/sources", json={
        "slug": "valley-news", "name": "Valley News", "source_type": "rss",
        "base_url": "https://example.com/feed", "languages": ["en"],
    })
    assert created.status_code == 201 and created.json()["state"] == "needs_review"
    refused = call(setup["admin"], "POST", f"/api/admin/reading/sources/{created.json()['id']}",
                   json={"state": "active", "polling_enabled": True})
    assert refused.status_code == 422
    assert refused.json()["detail"]["category"] == "reading_polling_not_allowed"


def test_polling_turns_on_for_an_approved_source_that_allows_automation(setup):
    created = call(setup["admin"], "POST", "/api/admin/reading/sources", json={
        "slug": "valley-news", "name": "Valley News", "source_type": "rss",
        "base_url": "https://example.com/feed", "languages": ["en"], "automation_allowed": True,
    }).json()
    enabled = call(setup["admin"], "POST", f"/api/admin/reading/sources/{created['id']}",
                   json={"state": "active", "polling_enabled": True})
    assert enabled.status_code == 200 and enabled.json()["polling_enabled"] is True


# ---- the learner side --------------------------------------------------------

def test_the_learner_list_is_lightweight_and_cacheable(setup):
    article_id = _publish_one(setup)
    response = call(setup["learner"], "GET", "/api/reading/articles?language=en", admin=False)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == article_id
    assert set(item) == {
        "id", "title", "language", "level", "topic", "reading_time_seconds",
        "excerpt", "word_count", "published_at", "content_revision",
    }
    assert "max-age" in response.headers["cache-control"]


def test_the_learner_list_is_bounded_however_much_is_asked_for(setup):
    _publish_one(setup)
    response = call(setup["learner"], "GET", "/api/reading/articles?language=en&limit=100000", admin=False)
    assert response.status_code == 200 and len(response.json()["items"]) <= 60


def test_the_learner_list_refuses_a_language_it_does_not_teach(setup):
    response = call(setup["learner"], "GET", "/api/reading/articles?language=kl", admin=False)
    assert response.status_code == 422


def test_the_learner_detail_carries_the_body_and_revalidates(setup):
    article_id = _publish_one(setup)
    first = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False)
    assert first.status_code == 200 and first.json()["body"].startswith("The river rose")
    etag = first.headers["etag"]
    again = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False,
                 headers={"if-none-match": etag})
    assert again.status_code == 304


def test_the_learner_detail_says_nothing_about_review_or_ingestion(setup):
    article_id = _publish_one(setup)
    body = call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).json()
    assert set(body) == {
        "id", "title", "body", "language", "level", "topic", "reading_time_seconds",
        "word_count", "content_revision", "published_at", "targets", "attribution",
    }


def test_an_unpublished_article_is_absent_from_the_learner_side(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    outcome = setup["engine"].process(setup["jobs"].claim("worker-1"))
    response = call(setup["learner"], "GET", f"/api/reading/articles/{outcome['article_id']}", admin=False)
    assert response.status_code == 404


def test_unpublishing_takes_it_back_off_the_learner_side(setup):
    article_id = _publish_one(setup)
    call(setup["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
         json={"status": "unpublished"})
    assert call(setup["learner"], "GET", "/api/reading/articles?language=en", admin=False).json()["items"] == []
    assert call(setup["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).status_code == 404


def test_there_is_no_learner_route_into_jobs_or_the_queue(setup):
    for path in ("/api/reading/articles/jobs", "/api/reading/articles/queue"):
        assert call(setup["learner"], "GET", path, admin=False).status_code == 404


# ---- operations --------------------------------------------------------------

def test_operations_counts_the_queue_without_carrying_payloads(setup):
    call(setup["admin"], "POST", "/api/admin/reading/jobs", data={"kind": "text", "text": ARTICLE})
    body = call(setup["admin"], "GET", "/api/admin/reading/operations").json()
    assert body["queue"]["queued"] == 1
    assert all("input_json" not in row for row in body["recent"])


def test_retry_makes_a_new_job_and_keeps_the_failure(setup):
    job = call(setup["admin"], "POST", "/api/admin/reading/jobs",
               data={"kind": "url", "url": "http://127.0.0.1:9/private"}).json()
    setup["engine"].process(setup["jobs"].claim("worker-1"))
    failed = call(setup["admin"], "GET", f"/api/admin/reading/jobs/{job['id']}").json()
    assert failed["status"] == "failed" and failed["last_error_code"] == "unsafe_url"
    retried = call(setup["admin"], "POST", f"/api/admin/reading/jobs/{job['id']}/retry")
    assert retried.status_code == 202 and retried.json()["id"] != job["id"]
    assert call(setup["admin"], "GET", f"/api/admin/reading/jobs/{job['id']}").json()["status"] == "failed"


def test_a_running_job_cannot_be_retried(setup):
    job = call(setup["admin"], "POST", "/api/admin/reading/jobs",
               data={"kind": "text", "text": ARTICLE}).json()
    setup["jobs"].claim("worker-1")
    refused = call(setup["admin"], "POST", f"/api/admin/reading/jobs/{job['id']}/retry")
    assert refused.status_code == 409


def test_the_engine_answers_503_before_its_schema_is_active(setup):
    """What an operator sees on a runtime where the migration is not applied:
    one truthful "not active yet", never a database error naming a table."""
    admin_api.configure_reading_admin(admin_guard=guard, content=None, jobs=None, engine=None)
    response = call(setup["admin"], "GET", "/api/admin/reading/queue")
    assert response.status_code == 503
    assert response.json()["detail"]["category"] == "reading_engine_unavailable"
    learner_api.configure_reading_articles(None)
    unavailable = call(setup["learner"], "GET", "/api/reading/articles?language=en", admin=False)
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["category"] == "reading_articles_unavailable"
