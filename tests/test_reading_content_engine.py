"""One pipeline from a submission to a candidate an admin can review.

The engine is what makes the adapters, the deterministic processor and the two
repositories one thing. What these tests hold: a submission becomes a job and
nothing else happens inside the request, the worker turns that job into exactly
one candidate, re-running the same input never produces a second one, a refusal
that will never succeed does not burn three attempts, and nothing in the
pipeline can publish.
"""
from __future__ import annotations

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")
from sqlalchemy import create_engine, event  # noqa: E402

from writing_coach.persistence.models import Base  # noqa: E402
from writing_coach.persistence.reading_content_repository import (  # noqa: E402
    ReadingContentRepository,
)
from writing_coach.persistence.reading_job_repository import ReadingJobRepository  # noqa: E402
from writing_coach.reading_content_engine import ReadingContentEngine  # noqa: E402
from writing_coach.reading_source_import import DirectUrlAdapter, ReadingSourceError, SubmittedInput  # noqa: E402
from writing_coach.reading_worker import ReadingWorker  # noqa: E402

ARTICLE = (
    "The river rose overnight and the fields were flooded by morning. "
    "Farmers moved their animals to higher ground before the water reached the road. "
    "The council opened the hall to families whose homes were cut off by the water. "
    "By Tuesday the level had fallen and volunteers began to clear the worst of the mud. "
    "Nobody was hurt, but several families will not return home before the end of the month. "
    "The mayor said the flood defences built last year had held everywhere except the old bridge. "
)

PAGE = f"<html><head><title>Rain returns</title></head><body><article><p>{ARTICLE}</p></article></body></html>"

ZH_ARTICLE = (
    "周末，我们来到山上的森林。老师带着学生沿着小路慢慢走进松树林。"
    "松树林里很安静，大家认真观察树木和地上的植物。远处有一片竹林，竹林旁边是一条清澈的小河。"
    "朋友拿出相机拍照，记录森林里的风景。老师解释保护环境的重要性，也介绍了几种常见的植物。"
    "大家把带来的食物和水放在书包里，没有在森林里留下垃圾。回家以后，学生写下观察到的事情。"
)


def _cleared_source(content, *, automation=True, republish=True):
    source = content.create_source(slug="owned-test", name="Authored test source", source_type="manual",
        base_url="", languages=["en", "zh"], rights={"can_republish": republish,
        "can_adapt": True, "attribution_required": False, "automation_allowed": automation}, created_by="admin")
    content.set_source_state(source["id"], "active", actor="admin")
    return source


@pytest.mark.parametrize("language,body", [("en", ARTICLE), ("zh", ZH_ARTICLE)])
def test_cleared_registered_source_prepares_and_publishes_once(engine_parts, language, body):
    engine, content, jobs = engine_parts
    source = _cleared_source(content)
    submitted = SubmittedInput(kind="text", title="A source-owned article", text=body,
        language=language, source_id=source["id"])
    job = engine.submit(submitted, actor="admin")
    result = engine.process(jobs.claim("worker"))
    article = content.get_article(result["article_id"])
    assert article["status"] == "published"
    assert article["analysis"]["admission"]["reasons"] == []
    assert article["source"]["rights_state"]["can_republish"] == "allowed"
    public = content.get_published_article(article["id"])
    assert len(public["targets"]) >= 3
    revision = article["content_revision"]
    again = engine.submit(submitted, actor="admin")
    assert again["id"] != job["id"]
    duplicate = engine.process(jobs.claim("worker"))
    assert duplicate["result_kind"] == "duplicate"
    assert duplicate["article_id"] == article["id"]
    assert content.get_article(article["id"])["content_revision"] == revision


@pytest.mark.parametrize("automation,republish,body,rights", [
    (False, True, ARTICLE, {}), (True, False, ARTICLE, {}),
    (True, True, "A short paste.", {}), (True, True, ARTICLE, {"can_republish": False}),
])
def test_automatic_admission_holds_ineligible_content_for_review(engine_parts, automation, republish, body, rights):
    engine, content, jobs = engine_parts
    source = _cleared_source(content, automation=automation, republish=republish)
    engine.submit(SubmittedInput(kind="text", text=body, language="en", source_id=source["id"], rights=rights), actor="admin")
    result = engine.process(jobs.claim("worker"))
    article = content.get_article(result["article_id"])
    assert article["status"] == "needs_review"
    assert article["analysis"]["admission"]["reasons"]
    assert content.get_published_article(article["id"]) is None


def test_registered_source_is_refused_before_work_when_inactive(engine_parts):
    engine, content, _jobs = engine_parts
    source = _cleared_source(content)
    content.set_source_state(source["id"], "paused", actor="admin")
    with pytest.raises(ReadingSourceError, match="active"):
        engine.submit(SubmittedInput(kind="text", text=ARTICLE, source_id=source["id"]), actor="admin")


def test_pausing_source_after_submission_holds_the_candidate(engine_parts):
    engine, content, jobs = engine_parts
    source = _cleared_source(content)
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, language="en", source_id=source["id"]), actor="admin")
    content.set_source_state(source["id"], "paused", actor="admin")
    result = engine.process(jobs.claim("worker"))
    article = content.get_article(result["article_id"])
    assert article["status"] == "needs_review"
    assert "source_not_active" in article["analysis"]["admission"]["reasons"]


def test_repeated_registered_input_does_not_analyze_again(engine_parts, monkeypatch):
    engine, content, jobs = engine_parts
    source = _cleared_source(content)
    submitted = SubmittedInput(kind="text", text=ARTICLE, language="en", source_id=source["id"])
    engine.submit(submitted, actor="admin")
    first = engine.process(jobs.claim("worker"))
    def forbidden(*args, **kwargs):
        raise AssertionError("Duplicate source must reuse the existing candidate")
    monkeypatch.setattr(ReadingContentEngine, "_build_candidate", forbidden)
    engine.submit(submitted, actor="admin")
    repeated = engine.process(jobs.claim("worker"))
    assert repeated["article_id"] == first["article_id"]
    assert repeated["result_kind"] == "duplicate"


def test_lost_precheck_race_reports_reuse_without_republishing(engine_parts, monkeypatch):
    engine, content, jobs = engine_parts
    source = _cleared_source(content)
    submitted = SubmittedInput(kind="text", text=ARTICLE, language="en", source_id=source["id"])
    engine.submit(submitted, actor="admin")
    first = engine.process(jobs.claim("worker"))
    from writing_coach.persistence.reading_content_repository import ReadingContentRepository
    monkeypatch.setattr(ReadingContentRepository, "article_for_source_item", lambda *args: None)
    engine.submit(submitted, actor="admin")
    repeated = engine.process(jobs.claim("worker"))
    assert repeated["result_kind"] == "duplicate"
    assert repeated["article_id"] == first["article_id"]
    assert content.get_article(first["article_id"])["content_revision"] == 1


def test_duplicate_import_cannot_silently_ignore_an_explicit_rights_denial(engine_parts):
    engine, content, jobs = engine_parts
    source = _cleared_source(content)
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, language="en", source_id=source["id"]), actor="admin")
    first = engine.process(jobs.claim("worker"))
    refused = engine.submit(SubmittedInput(kind="text", text=ARTICLE, language="en", source_id=source["id"],
                                         rights={"can_republish": False}), actor="admin")
    engine.process(jobs.claim("worker"))
    job = jobs.get_job(refused["id"])
    assert job["status"] == "failed"
    assert job["last_error_code"] == "reading_rights_conflict"
    assert job["attempt"] == 1
    assert content.get_article(first["article_id"])["status"] == "published"
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, language="en", source_id=source["id"],
                                rights={"can_republish": True}), actor="admin")
    assert engine.process(jobs.claim("worker"))["result_kind"] == "duplicate"


@pytest.fixture()
def engine_parts(tmp_path):
    db = create_engine(f"sqlite+pysqlite:///{tmp_path / 'engine.db'}")

    @event.listens_for(db, "connect")
    def _foreign_keys(dbapi_connection, record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db)
    content = ReadingContentRepository(db)
    content.ensure_built_in_sources()
    jobs = ReadingJobRepository(db)
    engine = ReadingContentEngine(content=content, jobs=jobs)
    return engine, content, jobs


def _fetcher(body: str, content_type: str = "text/html"):
    def fetch(url, *, max_bytes, timeout, content_types):
        return body.encode("utf-8"), content_type

    return fetch


# ---- submission -------------------------------------------------------------

def test_a_submission_returns_a_job_and_does_no_work_in_the_request(engine_parts):
    engine, content, jobs = engine_parts
    submitted = SubmittedInput(kind="text", text=ARTICLE, title="Rain returns", language="en",
                               rights={"can_republish": True})
    accepted = engine.submit(submitted, actor="admin@example.com")
    assert accepted["status"] == "queued" and accepted["duplicate"] is False
    assert content.list_queue()["items"] == []
    assert jobs.get_job(accepted["id"])["stage"] == "queued"


def test_a_double_submitted_form_is_one_job(engine_parts):
    engine, _content, _jobs = engine_parts
    submitted = SubmittedInput(kind="text", text=ARTICLE, rights={})
    first = engine.submit(submitted, actor="admin@example.com")
    second = engine.submit(submitted, actor="admin@example.com")
    assert second["duplicate"] is True and second["id"] == first["id"]


def test_an_unsupported_input_is_refused_at_submission_not_queued(engine_parts):
    engine, _content, jobs = engine_parts
    with pytest.raises(Exception) as failure:
        engine.submit(SubmittedInput(kind="telepathy", rights={}), actor="admin@example.com")
    assert getattr(failure.value, "code", "") == "unsupported_input"
    assert jobs.list_jobs()["items"] == []


# ---- processing -------------------------------------------------------------

def test_a_pasted_text_becomes_one_candidate_waiting_for_review(engine_parts):
    engine, content, jobs = engine_parts
    job = engine.submit(
        SubmittedInput(kind="text", text=ARTICLE, title="Rain returns", language="en", rights={}),
        actor="admin@example.com",
    )
    outcome = engine.process(jobs.claim("worker-1"))
    assert outcome["result_kind"] == "article_created"
    article = content.get_article(outcome["article_id"])
    assert article["status"] == "needs_review"
    assert article["title"] == "Rain returns"
    assert article["estimated_level"] and article["effective_level"] == article["estimated_level"]
    assert article["word_count"] > 0 and article["reading_time_seconds"] > 0
    assert 1 <= len(article["targets"]) <= 8
    assert jobs.get_job(job["id"])["status"] == "completed"


def test_the_candidate_records_the_quality_problems_a_reviewer_should_see(engine_parts):
    engine, content, jobs = engine_parts
    engine.submit(
        SubmittedInput(kind="text", text="今天天气很好，我们去公园散步，然后回家吃饭。" * 6,
                       language="en", rights={}),
        actor="admin@example.com",
    )
    outcome = engine.process(jobs.claim("worker-1"))
    article = content.get_article(outcome["article_id"])
    assert "language_mismatch" in article["analysis"]["quality_issues"]


def test_rights_that_were_never_answered_are_visible_on_the_candidate(engine_parts):
    engine, content, jobs = engine_parts
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, rights={}), actor="admin@example.com")
    outcome = engine.process(jobs.claim("worker-1"))
    article = content.get_article(outcome["article_id"])
    assert article["source"]["metadata"]["rights_known"] is False


def test_a_url_job_fetches_through_the_guarded_fetcher(engine_parts):
    engine, content, jobs = engine_parts
    engine.adapters["url"] = lambda: DirectUrlAdapter(fetcher=_fetcher(PAGE))
    engine.submit(
        SubmittedInput(kind="url", url="https://example.com/news/rain?utm_source=x", rights={}),
        actor="admin@example.com",
    )
    outcome = engine.process(jobs.claim("worker-1"))
    article = content.get_article(outcome["article_id"])
    assert article["title"] == "Rain returns"
    assert article["source"]["canonical_url"] == "https://example.com/news/rain"


def test_the_same_text_twice_never_becomes_two_candidates(engine_parts):
    engine, content, jobs = engine_parts
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, rights={}), actor="admin@example.com")
    first = engine.process(jobs.claim("worker-1"))
    # A second job for the same bytes: a different submission, same content.
    engine.submit(
        SubmittedInput(kind="text", text=ARTICLE, title="Same text, new submission", rights={}),
        actor="admin@example.com",
    )
    second = engine.process(jobs.claim("worker-1"))
    assert second["result_kind"] == "duplicate"
    assert second["article_id"] == first["article_id"]
    assert len(content.list_queue()["items"]) == 1


def test_a_text_already_rejected_does_not_come_back_as_new(engine_parts):
    engine, content, jobs = engine_parts
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, rights={}), actor="admin@example.com")
    first = engine.process(jobs.claim("worker-1"))
    content.set_status(first["article_id"], "rejected", actor="admin@example.com", reason="not suitable")
    engine.submit(
        SubmittedInput(kind="text", text=ARTICLE, title="Trying again", rights={}),
        actor="admin@example.com",
    )
    second = engine.process(jobs.claim("worker-1"))
    assert second["result_kind"] == "duplicate"
    assert content.get_article(second["article_id"])["status"] == "rejected"


def test_the_pipeline_cannot_publish(engine_parts):
    engine, content, jobs = engine_parts
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, rights={}), actor="admin@example.com")
    engine.process(jobs.claim("worker-1"))
    assert content.list_published(language="en")["items"] == []
    assert content.published_count() == 0


# ---- failure ----------------------------------------------------------------

def test_a_refusal_that_can_never_succeed_does_not_burn_three_attempts(engine_parts):
    engine, _content, jobs = engine_parts
    engine.submit(
        SubmittedInput(kind="url", url="http://127.0.0.1:8000/admin", rights={}),
        actor="admin@example.com",
    )
    engine.process(jobs.claim("worker-1"))
    failed = jobs.list_jobs()["items"][0]
    assert failed["status"] == "failed" and failed["last_error_code"] == "unsafe_url"
    assert jobs.claim("worker-1") is None


def test_a_transient_failure_comes_back_for_another_attempt(engine_parts):
    engine, _content, jobs = engine_parts

    def failing_fetcher(url, *, max_bytes, timeout, content_types):
        from writing_coach.media_safe_fetch import UnsafeMediaFetch

        raise UnsafeMediaFetch("The media address could not be fetched.")

    engine.adapters["url"] = lambda: DirectUrlAdapter(fetcher=failing_fetcher)
    job = engine.submit(
        SubmittedInput(kind="url", url="https://example.com/news/rain", rights={}),
        actor="admin@example.com",
    )
    engine.process(jobs.claim("worker-1"))
    again = jobs.get_job(job["id"])
    assert again["status"] == "queued" and again["attempt"] == 1
    assert again["last_error_code"] == "fetch_failed"


def test_an_unexpected_error_is_a_failure_not_a_lost_job(engine_parts):
    engine, _content, jobs = engine_parts

    def exploding_fetcher(url, *, max_bytes, timeout, content_types):
        raise RuntimeError("something nobody predicted")

    engine.adapters["url"] = lambda: DirectUrlAdapter(fetcher=exploding_fetcher)
    job = engine.submit(
        SubmittedInput(kind="url", url="https://example.com/news/rain", rights={}),
        actor="admin@example.com",
    )
    engine.process(jobs.claim("worker-1"))
    recorded = jobs.get_job(job["id"])
    assert recorded["last_error_code"] == "internal_error"
    assert recorded["status"] in {"queued", "failed"}


# ---- the worker -------------------------------------------------------------

def test_the_worker_takes_one_job_and_reports_what_it_did(engine_parts):
    engine, content, jobs = engine_parts
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, rights={}), actor="admin@example.com")
    worker = ReadingWorker(engine=engine, jobs=jobs, worker_id="worker-1")
    assert worker.run_once()["result_kind"] == "article_created"
    assert worker.run_once() is None
    assert len(content.list_queue()["items"]) == 1


def test_the_worker_recovers_a_job_a_crashed_worker_was_holding(engine_parts):
    from datetime import UTC, datetime, timedelta

    engine, content, jobs = engine_parts
    engine.submit(SubmittedInput(kind="text", text=ARTICLE, rights={}), actor="admin@example.com")
    jobs.claim("worker-that-died")
    worker = ReadingWorker(engine=engine, jobs=jobs, worker_id="worker-2", stale_after=timedelta(minutes=5))
    later = datetime.now(UTC) + timedelta(minutes=10)
    assert worker.run_once(now=later)["result_kind"] == "article_created"
    assert len(content.list_queue()["items"]) == 1


def test_worker_concurrency_is_configurable_and_bounded(monkeypatch):
    from writing_coach import reading_worker

    monkeypatch.setenv("READING_WORKER_CONCURRENCY", "4")
    assert reading_worker.configured_concurrency() == 4
    monkeypatch.setenv("READING_WORKER_CONCURRENCY", "0")
    assert reading_worker.configured_concurrency() == 1
    monkeypatch.setenv("READING_WORKER_CONCURRENCY", "nonsense")
    assert reading_worker.configured_concurrency() == 1
    monkeypatch.delenv("READING_WORKER_CONCURRENCY")
    assert reading_worker.configured_concurrency() == 1
