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
from writing_coach.reading_source_import import DirectUrlAdapter, SubmittedInput  # noqa: E402
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
