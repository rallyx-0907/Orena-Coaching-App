"""Canonical Reading over HTTP: the Admin's comprehension sets and rights
warnings, and the learner's practice - on a real SQLite schema.

What these hold: the AI processor writes questions for a published passage and
never a passage; nothing reaches a learner until an Admin approves it; a
publish over rights warnings is recorded beside the warnings; the learner
never sees an answer before their attempt is saved; learner submit is off until
it is switched on (D-076), and off it writes nothing; a retried submit is one
attempt. English and Chinese take the same routes.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.pool import StaticPool

from writing_coach import reading_admin_api as admin_api
from writing_coach import reading_practice_api as practice_api
from writing_coach.persistence.models import Base, ReadingAttempt
from writing_coach.persistence.reading_content_repository import ReadingContentRepository
from writing_coach.persistence.reading_evidence_repository import ReadingEvidenceRepository
from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_content_engine import ReadingContentEngine

ADMIN = {"google_sub": "sub-admin", "email": "admin@example.com", "role": "admin"}
BODIES = {
    "en": (
        "Tom missed the early train. He waited forty minutes on a cold platform. "
        "When the next train came, it was full, so he stood all the way to the city."
    ),
    "zh": "小明错过了早班火车。他在寒冷的站台上等了四十分钟。下一班火车来的时候已经满了，所以他一路站到城里。",
}
SPANS = {"en": ("forty minutes", "it was full"), "zh": ("四十分钟", "已经满了")}


def guard(request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "Platform administrator access required")
    return ADMIN


def _draft(language: str, *, grounded: bool = True) -> dict:
    first, second = SPANS[language]
    if not grounded:
        first = second = "words the passage never says"
    return {"questions": [
        {"question_type": "detail", "prompt": "How long?", "options": ["forty", "ten", "sixty", "five"],
         "correct_index": 0, "explanation": "Anh ấy đợi bốn mươi phút.", "evidence_text": first},
        {"question_type": "inference", "prompt": "Why stand?", "options": ["full", "late", "broken", "cold"],
         "correct_index": 0, "explanation": "Tàu đã đầy.", "evidence_text": second},
        {"question_type": "main_idea", "prompt": "About?", "options": ["a journey", "a meal", "a race", "a game"],
         "correct_index": 0, "explanation": "Một chuyến đi.", "evidence_text": ""},
    ]}


class Provider:
    """A stand-in for the configured AI provider: it answers with a draft and
    records what it was asked, so a test can see it was never asked to write a
    passage."""

    def __init__(self) -> None:
        self.grounded = True
        self.calls: list[dict] = []

    def __call__(self, *, messages, schema, max_output_tokens, temperature, capability_key):
        self.calls.append({"messages": messages, "schema": schema, "capability_key": capability_key})
        language = "zh" if "questions in Chinese" in messages[0]["content"] else "en"
        return SimpleNamespace(data=_draft(language, grounded=self.grounded), model="stub-model")


class Scope:
    user = "learner-a"
    language = "en"
    support = "vi"
    submit = False


@pytest.fixture()
def setup():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    content = ReadingContentRepository(engine)
    content.ensure_built_in_sources()
    jobs = ReadingJobRepository(engine)
    scope = Scope()
    evidence = ReadingEvidenceRepository(
        engine, user_key_provider=lambda: scope.user, language_provider=lambda: scope.language
    )
    provider = Provider()
    audited: list[dict] = []

    def audit(action, *, actor_key, entity_type="", entity_id="", payload=None):
        audited.append({"action": action, "entity_id": entity_id, "payload": dict(payload or {})})

    admin_api.configure_reading_admin(
        admin_guard=guard, content=content, jobs=jobs,
        engine=ReadingContentEngine(content=content, jobs=jobs), audit=audit,
        evidence=evidence, generate=provider,
    )
    practice_api.configure_reading_practice(
        evidence, support_language=lambda: scope.support, submit_enabled=lambda: scope.submit
    )
    app = FastAPI()
    app.include_router(admin_api.router)
    app.include_router(practice_api.router)
    yield SimpleNamespace(app=app, engine=engine, content=content, evidence=evidence, scope=scope,
                          provider=provider, audited=audited)
    admin_api.configure_reading_admin(admin_guard=None)
    practice_api.configure_reading_practice(None, support_language=None,
                                            submit_enabled=lambda: False)


def call(app, method, path, *, admin=True, **kwargs):
    headers = {"x-test-admin": "1"} if admin else {}
    if method.upper() != "GET":
        headers["origin"] = "http://testserver"

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run())


def _article(setup, language="en", *, rights=None, level="B1"):
    snapshot = setup.content.record_source_item(
        source_id=setup.content.built_in_source_id("manual"), source_native_id="", canonical_url="",
        title="Train", author="", published_at=None, language=language, body=BODIES[language],
        content_hash=(language * 64)[:64] if rights is None else ("f" * 64), metadata={},
        rights=rights if rights is not None else {},
    )
    article = setup.content.create_article(
        source_item_id=snapshot["id"], title="The late train", body=BODIES[language], excerpt="",
        language=language, topic="travel", estimated_level=level, estimated_confidence=0.7,
        word_count=30, reading_time_seconds=60, analysis={}, targets=[],
    )
    return article["id"]


def _publish(setup, article_id):
    response = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}/status",
                    json={"status": "published"})
    assert response.status_code == 200, response.text
    return response.json()


def _approved_set(setup, article_id, support="vi"):
    created = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}/comprehension-sets",
                   json={"support_language": support})
    assert created.status_code == 201, created.text
    set_id = created.json()["id"]
    assert call(setup.app, "POST", f"/api/admin/reading/comprehension-sets/{set_id}/status",
                json={"status": "needs_review"}).status_code == 200
    for question in created.json()["questions"]:
        decided = call(setup.app, "POST",
                       f"/api/admin/reading/comprehension-sets/{set_id}/questions/{question['id']}",
                       json={"decision": "approve"})
        assert decided.status_code == 200, decided.text
    approved = call(setup.app, "POST", f"/api/admin/reading/comprehension-sets/{set_id}/status",
                    json={"status": "approved"})
    assert approved.status_code == 200, approved.text
    return set_id


def _attempts(setup) -> int:
    with setup.engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(ReadingAttempt)).scalar_one()


# ---- rights warnings ------------------------------------------------------------

def test_publishing_over_rights_warnings_is_allowed_and_recorded_beside_them(setup):
    article_id = _article(setup)
    published = _publish(setup, article_id)
    codes = {item["code"] for item in published["publication_warnings"]}
    assert codes == {"rights_unknown", "attribution_unknown"}
    assert published["status"] == "published"
    record = next(item for item in setup.audited if item["action"] == "admin.reading_article_published")
    assert record["payload"]["override"] is True
    assert {item["code"] for item in record["payload"]["warnings"]} == codes
    event = next(item for item in setup.content.list_review_events(article_id) if item["action"] == "published")
    assert event["changes"]["published_over_warnings"] is True


def test_a_cleared_article_publishes_with_no_warning(setup):
    article_id = _article(setup, rights={"can_republish": True, "attribution_required": False})
    published = _publish(setup, article_id)
    assert published["publication_warnings"] == []
    record = next(item for item in setup.audited if item["action"] == "admin.reading_article_published")
    assert record["payload"]["override"] is False


def test_a_refused_permission_is_a_strong_warning_not_a_block(setup):
    article_id = _article(setup, rights={"can_republish": False, "attribution_required": True})
    published = _publish(setup, article_id)
    assert {"code": "rights_not_cleared", "level": "strong"} in published["publication_warnings"]


# ---- content type ------------------------------------------------------------------

def test_the_content_type_is_the_learner_facing_kind_only(setup):
    article_id = _article(setup)
    edited = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}", json={"content_kind": "news"})
    assert edited.status_code == 200 and edited.json()["content_kind"] == "news"
    for bad in ("blog", "publisher", "rss"):
        refused = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}", json={"content_kind": bad})
        assert refused.status_code == 422
        assert refused.json()["detail"]["category"] == "reading_invalid_content_kind"


# ---- comprehension sets ---------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "zh"])
def test_the_processor_asks_questions_about_a_passage_and_never_writes_one(setup, language):
    article_id = _article(setup, language)
    _publish(setup, article_id)
    created = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}/comprehension-sets",
                   json={"support_language": "vi"})
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "draft" and body["language_code"] == language
    assert len(body["questions"]) == 3
    asked = setup.provider.calls[-1]
    assert asked["capability_key"] == "reading_generator"
    assert "never rewrite" in asked["messages"][0]["content"]
    assert BODIES[language] in asked["messages"][1]["content"]
    assert set(asked["schema"]["properties"]) == {"questions"}, "the provider is never asked for a passage"
    listed = call(setup.app, "GET", f"/api/admin/reading/articles/{article_id}/comprehension-sets").json()
    assert [item["id"] for item in listed["items"]] == [body["id"]]
    assert any(item["action"] == "admin.reading_comprehension_set_created" for item in setup.audited)


def test_an_ungrounded_draft_or_no_provider_is_refused_and_writes_nothing(setup):
    article_id = _article(setup)
    setup.provider.grounded = False
    refused = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}/comprehension-sets",
                   json={"support_language": "vi"})
    assert refused.status_code == 422
    assert refused.json()["detail"]["category"] == "reading_processor_ungrounded"
    admin_api._state.generate = None
    unavailable = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}/comprehension-sets",
                       json={"support_language": "vi"})
    assert unavailable.status_code == 503
    assert unavailable.json()["detail"]["category"] == "reading_processor_unavailable"
    assert setup.evidence.list_sets(article_id) == []


def test_an_approved_set_is_archived_never_discarded_and_needs_a_reason_to_reject(setup):
    article_id = _article(setup)
    _publish(setup, article_id)
    set_id = _approved_set(setup, article_id)
    refused = call(setup.app, "POST", f"/api/admin/reading/comprehension-sets/{set_id}/discard")
    assert refused.status_code == 409
    assert refused.json()["detail"]["category"] == "reading_set_undeletable"
    other = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}/comprehension-sets",
                 json={"support_language": "zh"}).json()["id"]
    call(setup.app, "POST", f"/api/admin/reading/comprehension-sets/{other}/status", json={"status": "needs_review"})
    no_reason = call(setup.app, "POST", f"/api/admin/reading/comprehension-sets/{other}/status",
                     json={"status": "rejected"})
    assert no_reason.status_code == 422
    assert call(setup.app, "POST", f"/api/admin/reading/comprehension-sets/{other}/discard").status_code == 200
    archived = call(setup.app, "POST", f"/api/admin/reading/comprehension-sets/{set_id}/status",
                    json={"status": "archived"})
    assert archived.status_code == 200 and archived.json()["status"] == "archived"


def test_every_set_route_requires_an_administrator(setup):
    article_id = _article(setup)
    for method, path in (("GET", f"/api/admin/reading/articles/{article_id}/comprehension-sets"),
                         ("POST", f"/api/admin/reading/articles/{article_id}/comprehension-sets")):
        assert call(setup.app, method, path, admin=False, json={"support_language": "vi"}).status_code == 403


# ---- the learner ------------------------------------------------------------------------

@pytest.mark.parametrize("language", ["en", "zh"])
def test_the_learner_meets_the_set_without_answers_and_submit_starts_disabled(setup, language):
    setup.scope.language = language
    article_id = _article(setup, language, level="HSK3" if language == "zh" else "B1")
    _publish(setup, article_id)
    _approved_set(setup, article_id)
    served = call(setup.app, "GET", f"/api/reading/practice/articles/{article_id}", admin=False)
    assert served.status_code == 200
    payload = served.json()
    assert payload["submit_enabled"] is False
    for question in payload["set"]["questions"]:
        assert not {"correct_index", "explanation", "evidence_text"} & set(question)
    answers = {question["id"]: 0 for question in payload["set"]["questions"]}
    refused = call(setup.app, "POST", "/api/reading/practice/attempts", admin=False,
                   json={"set_id": payload["set"]["id"], "operation_id": "op-1", "answers": answers})
    assert refused.status_code == 503
    assert refused.json()["detail"]["category"] == "reading_submit_disabled"
    assert _attempts(setup) == 0


@pytest.mark.parametrize("language", ["en", "zh"])
def test_a_submitted_sheet_is_scored_saved_once_and_answered_with_its_key(setup, language):
    setup.scope.language, setup.scope.submit = language, True
    article_id = _article(setup, language, level="HSK3" if language == "zh" else "B1")
    _publish(setup, article_id)
    _approved_set(setup, article_id)
    served = call(setup.app, "GET", f"/api/reading/practice/articles/{article_id}", admin=False).json()["set"]
    answers = {question["id"]: (0 if index else 1) for index, question in enumerate(served["questions"])}
    body = {"set_id": served["id"], "operation_id": "sheet-1", "answers": answers}
    first = call(setup.app, "POST", "/api/reading/practice/attempts", admin=False, json=body)
    assert first.status_code == 200, first.text
    saved = first.json()
    assert saved["replayed"] is False
    assert saved["attempt"]["correct_count"] == 2 and saved["attempt"]["total"] == 3
    results = saved["results"]
    assert [item["question_id"] for item in results] == [question["id"] for question in served["questions"]]
    assert [item["correct"] for item in results] == [False, True, True]
    assert all(item["correct_index"] == 0 for item in results)
    assert results[0]["evidence_fragment"] == SPANS[language][0]
    assert results[0]["explanation"]
    retry = call(setup.app, "POST", "/api/reading/practice/attempts", admin=False, json=body)
    assert retry.status_code == 200 and retry.json()["replayed"] is True
    assert retry.json()["attempt"] == saved["attempt"]
    assert _attempts(setup) == 1
    reused = call(setup.app, "POST", "/api/reading/practice/attempts", admin=False,
                  json={**body, "answers": {key: 2 for key in answers}})
    assert reused.status_code == 409
    assert reused.json()["detail"]["category"] == "reading_operation_reused"
    evidence = call(setup.app, "GET", "/api/reading/practice/evidence", admin=False).json()["items"]
    assert [item["article_id"] for item in evidence] == [article_id]
    ability = call(setup.app, "GET", "/api/reading/practice/ability", admin=False).json()
    assert ability["attempts"] == 1 and ability["language_code"] == language
    # The only article is attempted: nothing is left to choose.
    assert call(setup.app, "GET", "/api/reading/practice/next", admin=False).json()["available"] is False


def test_a_stale_set_refuses_a_new_submit_with_its_reason(setup):
    setup.scope.submit = True
    article_id = _article(setup)
    _publish(setup, article_id)
    set_id = _approved_set(setup, article_id)
    served = call(setup.app, "GET", f"/api/reading/practice/articles/{article_id}", admin=False).json()["set"]
    edited = call(setup.app, "POST", f"/api/admin/reading/articles/{article_id}",
                  json={"body": BODIES["en"] + " He was tired."})
    assert edited.status_code == 200
    assert setup.evidence.get_set(set_id)["status"] == "stale"
    assert call(setup.app, "GET", f"/api/reading/practice/articles/{article_id}", admin=False).status_code == 404
    late = call(setup.app, "POST", "/api/reading/practice/attempts", admin=False,
                json={"set_id": served["id"], "operation_id": "late",
                      "answers": {question["id"]: 0 for question in served["questions"]}})
    assert late.status_code == 422
    assert late.json()["detail"]["category"] == "reading_set_stale"
    assert _attempts(setup) == 0
