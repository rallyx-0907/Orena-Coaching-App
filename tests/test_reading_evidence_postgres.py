"""Canonical Reading on PostgreSQL: the lock order, proved under contention.

Runs when `ORENA_TEST_POSTGRES_URL` names a throwaway database: the real chain
`20260811_0001 -> 20260924_0016` in a fresh schema, then the repositories the
runtime uses, from several connections at once.

The documented order (proposal §5.1/§6) is: the per-(account, language)
advisory lock, then the article row, then the set, then the insert. A body
edit takes the article `FOR UPDATE` first; a submit takes it `FOR SHARE`
before the set. What this proves:

- a submit that arrives while a body edit holds the article waits for it, then
  sees the edit - the set is stale, nothing is recorded against a body the
  learner did not read;
- a body edit that arrives while a submit holds the article waits for the
  submit, then stales the set - the recorded attempt stays, anchored to the
  body it was answered against;
- many retries of one submit, all at once, record one attempt;
- submits and edits interleaved at random never deadlock.

    ORENA_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@host/throwaway \\
        python -m pytest tests/test_reading_evidence_postgres.py
"""
from __future__ import annotations

import os
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")
from sqlalchemy import create_engine, func, select, text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from writing_coach.persistence.models import ReadingArticle, ReadingAttempt  # noqa: E402
from writing_coach.persistence.reading_content_repository import (  # noqa: E402
    ReadingContentRepository,
    TargetInput,
)
from writing_coach.persistence.reading_evidence_repository import (  # noqa: E402
    QuestionInput,
    ReadingEvidenceRepository,
    body_sha256,
    stale_sets_for_body,
)

ROOT = Path(__file__).resolve().parents[1]
URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

BODY = (
    "Tom missed the early train. He waited forty minutes on a cold platform. "
    "When the next train came, it was full, so he stood all the way to the city."
)
EDITED = BODY + " He was tired."


def _schema_url(schema: str) -> str:
    separator = "&" if "?" in URL else "?"
    return f"{URL}{separator}options={quote(f'-csearch_path={schema}')}"


@contextmanager
def _database():
    from alembic import command
    from alembic.config import Config

    admin = create_engine(URL, future=True)
    schema = f"reading_lock_{uuid.uuid4().hex[:10]}"
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        cfg = Config(str(ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(ROOT / "migrations"))
        cfg.set_main_option("path_separator", "os")
        cfg.set_main_option("sqlalchemy.url", _schema_url(schema).replace("%", "%%"))
        command.upgrade(cfg, "20260924_0016")
        engine = create_engine(_schema_url(schema), future=True, pool_size=20, max_overflow=10)
        try:
            yield engine
        finally:
            engine.dispose()
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture(scope="module")
def engine():
    with _database() as built:
        yield built


def _repositories(engine, user="learner-a", language="en"):
    content = ReadingContentRepository(engine)
    content.ensure_built_in_sources()
    evidence = ReadingEvidenceRepository(engine, user_key_provider=lambda: user,
                                         language_provider=lambda: language)
    return content, evidence


def _anchor(content, article_id) -> str:
    """The hash of the body the questions are written from - what the Admin
    route takes before it asks the AI."""
    return body_sha256(content.get_article(article_id)["body"])


def _approved(engine):
    content, evidence = _repositories(engine)
    snapshot = content.record_source_item(
        source_id=content.built_in_source_id("manual"), source_native_id="", canonical_url="", title="T",
        author="", published_at=None, language="en", body=BODY, content_hash=uuid.uuid4().hex * 2,
        metadata={}, rights={"can_republish": True},
    )
    article = content.create_article(
        source_item_id=snapshot["id"], title="T", body=BODY, excerpt="", language="en", topic="travel",
        estimated_level="B1", estimated_confidence=0.7, word_count=30, reading_time_seconds=60, analysis={},
        targets=[TargetInput(text="forty minutes", canonical_form="forty minutes", target_type="phrase",
                             context="", estimated_level="", rank=0)],
    )
    content.set_status(article["id"], "published", actor="admin")
    built = evidence.create_set(article["id"], expected_body_sha256=_anchor(content, article["id"]), support_language="vi", generator_version="test/1", model="stub",
                                questions=[
                                    QuestionInput("detail", "How long?", ["forty", "ten", "five"], 0, "x",
                                                  "forty minutes"),
                                    QuestionInput("main_idea", "About?", ["a trip", "a meal"], 0, "y", None,
                                                  rank=1),
                                ], validation={}, actor="admin")
    evidence.transition(built["id"], "needs_review", actor="admin")
    for question in built["questions"]:
        evidence.decide_question(built["id"], question["id"], decision="approve", actor="admin")
    evidence.transition(built["id"], "approved", actor="admin")
    answers = {question["id"]: 0 for question in built["questions"]}
    return article["id"], built["id"], answers


def _attempts(engine, set_id) -> int:
    with engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(ReadingAttempt)
                                  .where(ReadingAttempt.set_id == uuid.UUID(set_id))).scalar_one()


def _waiting(engine, timeout=5.0) -> bool:
    """Whether some backend in this database is waiting on a lock."""
    deadline = time.monotonic() + timeout
    with engine.connect() as connection:
        while time.monotonic() < deadline:
            waiting = connection.execute(text(
                "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock' "
                "AND datname = current_database()")).scalar_one()
            if waiting:
                return True
            time.sleep(0.05)
    return False


def test_a_submit_waits_for_a_body_edit_and_then_sees_it(engine):
    article_id, set_id, answers = _approved(engine)
    _, evidence = _repositories(engine)
    result: dict = {}
    with engine.connect() as edit:
        transaction = edit.begin()
        # The edit's first step: the article, FOR UPDATE.
        edit.execute(select(ReadingArticle.body).where(ReadingArticle.id == uuid.UUID(article_id))
                     .with_for_update()).scalar_one()
        submit = threading.Thread(target=lambda: result.update(outcome=evidence.submit_attempt(
            set_id=set_id, operation_id="during-edit", answers=answers, support_language="vi")))
        submit.start()
        assert _waiting(engine), "the submit must wait on the article the edit holds"
        assert submit.is_alive()
        edit.execute(ReadingArticle.__table__.update().where(ReadingArticle.id == uuid.UUID(article_id))
                     .values(body=EDITED))
        from datetime import UTC, datetime
        stale = stale_sets_for_body(edit, uuid.UUID(article_id), EDITED, actor="admin", now=datetime.now(UTC))
        assert stale == [set_id]
        transaction.commit()
    submit.join(10)
    assert not submit.is_alive()
    assert (result["outcome"].status, result["outcome"].reason) == ("rejected", "set_stale")
    assert _attempts(engine, set_id) == 0


def test_a_body_edit_waits_for_a_submit_and_then_stales_the_set(engine):
    article_id, set_id, answers = _approved(engine)
    content, evidence = _repositories(engine)
    result: dict = {}
    with engine.connect() as submit:
        transaction = submit.begin()
        # The submit's order: its advisory lock, the article FOR SHARE, the set FOR SHARE.
        submit.execute(text("SELECT pg_advisory_xact_lock(1380270404, hashtext('proof'))"))
        submit.execute(select(ReadingArticle.body).where(ReadingArticle.id == uuid.UUID(article_id))
                       .with_for_update(read=True)).scalar_one()
        edit = threading.Thread(target=lambda: result.update(article=content.update_article(
            article_id, actor="admin", body=EDITED)))
        edit.start()
        assert _waiting(engine), "the edit must wait on the article the submit holds"
        assert edit.is_alive()
        transaction.commit()
    edit.join(10)
    assert not edit.is_alive()
    assert result["article"]["body"] == EDITED
    assert evidence.get_set(set_id)["status"] == "stale"


def test_a_committed_attempt_survives_the_edit_that_follows_it(engine):
    article_id, set_id, answers = _approved(engine)
    content, evidence = _repositories(engine, user="learner-survives")
    recorded = evidence.submit_attempt(set_id=set_id, operation_id="before", answers=answers, support_language="vi")
    assert recorded.status == "committed"
    content.update_article(article_id, actor="admin", body=EDITED)
    listed = evidence.list_evidence()
    assert [item["id"] for item in listed] == [recorded.attempt["id"]]
    retry = evidence.submit_attempt(set_id=set_id, operation_id="before", answers=answers, support_language="vi")
    assert retry.replayed and retry.attempt == recorded.attempt


def test_a_recommendation_is_verified_and_spent_inside_the_submit(engine):
    """On PostgreSQL the recommendation is checked in the submit's own
    transaction, after the advisory lock: the recommended set records the
    policy's version even after other evidence landed first; the same set
    without it, or a second time, records none; and many submits presenting
    one recommendation at once spend it exactly once."""
    for _ in range(3):
        _approved(engine)
    _, evidence = _repositories(engine, user=f"learner-provenance-{uuid.uuid4().hex[:8]}")
    offer = evidence.next_article(support_language="vi")
    served = evidence.served_set(offer["article_id"], support_language="vi")
    answers = {question["id"]: 0 for question in served["questions"]}
    # Other evidence first, on a fresh article the learner picked.
    _, other_set, other_answers = _approved(engine)
    picked = evidence.submit_attempt(set_id=other_set, operation_id="picked", answers=other_answers,
                                     support_language="vi")
    assert picked.attempt["selection_policy_version"] is None

    results: list = []

    def submit(index: int) -> None:
        results.append(evidence.submit_attempt(set_id=offer["set_id"], operation_id=f"rec-{index}",
                                               answers=answers, support_language="vi",
                                               recommendation=offer["recommendation"]))

    threads = [threading.Thread(target=submit, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert len(results) == 4 and all(result.status == "committed" for result in results)
    counted = [result for result in results if result.attempt["selection_policy_version"] == "reading-select/1"]
    assert len(counted) == 1, "one recommendation is spent by exactly one attempt"
    plain = evidence.submit_attempt(set_id=offer["set_id"], operation_id="plain", answers=answers,
                                    support_language="vi")
    assert plain.attempt["selection_policy_version"] is None


def test_many_retries_of_one_submit_at_once_record_one_attempt(engine):
    _, set_id, answers = _approved(engine)
    _, evidence = _repositories(engine, user="learner-retries")
    barrier = threading.Barrier(8)

    def retry(_):
        barrier.wait()
        return evidence.submit_attempt(set_id=set_id, operation_id="one-sheet", answers=answers,
                                       support_language="vi")

    with ThreadPoolExecutor(8) as pool:
        outcomes = list(pool.map(retry, range(8)))
    assert {outcome.status for outcome in outcomes} == {"committed"}
    assert len({outcome.attempt["id"] for outcome in outcomes}) == 1
    assert sum(1 for outcome in outcomes if not outcome.replayed) == 1
    assert _attempts(engine, set_id) == 1
    assert evidence.ability()["attempts"] == 1


def test_submits_and_edits_interleaved_never_deadlock(engine):
    article_id, set_id, answers = _approved(engine)
    content, _ = _repositories(engine)
    rng = random.Random(7)
    errors: list[BaseException] = []

    def learner(index):
        _, evidence = _repositories(engine, user=f"storm-{index % 4}")
        try:
            outcome = evidence.submit_attempt(set_id=set_id, operation_id=f"storm-{index}", answers=answers,
                                              support_language="vi")
            assert outcome.status in {"committed", "rejected"}
            if outcome.status == "rejected":
                assert outcome.reason == "set_stale"
        except DBAPIError as exc:  # a deadlock surfaces here
            errors.append(exc)

    def editor(index):
        try:
            content.update_article(article_id, actor="admin", body=EDITED if index % 2 else BODY)
        except DBAPIError as exc:
            errors.append(exc)

    work = [(learner, index) for index in range(24)] + [(editor, index) for index in range(8)]
    rng.shuffle(work)
    with ThreadPoolExecutor(12) as pool:
        for future in [pool.submit(function, index) for function, index in work]:
            future.result(timeout=60)
    assert errors == [], errors
    # Every committed attempt was measured in ordinal order per account.
    with engine.connect() as connection:
        rows = connection.execute(select(ReadingAttempt.user_id, ReadingAttempt.ordinal)
                                  .where(ReadingAttempt.set_id == uuid.UUID(set_id))
                                  .order_by(ReadingAttempt.user_id, ReadingAttempt.ordinal)).all()
    by_user: dict = {}
    for user_id, ordinal in rows:
        by_user.setdefault(user_id, []).append(ordinal)
    for ordinals in by_user.values():
        assert ordinals == list(range(1, len(ordinals) + 1))
