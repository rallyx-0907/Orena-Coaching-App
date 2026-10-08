"""D4 slice 4: a grammar point's completion and its quiz result are ONE write (I11, D-104 H-4, D-105 H-20).

The repository method is what this slice ships; the route that accepts a Grammar Lab point id waits for
the published-grammar API (D-105 point 4), which is where the point is validated against the published
catalogue. Both backends run: SQLite (always) and PostgreSQL (when ORENA_TEST_POSTGRES_URL is set).
"""
from __future__ import annotations

import contextvars
import threading
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from writing_coach.persistence.auth_repository import PostgresAuthRepository
from writing_coach.persistence.learning_repository import (
    PostgresLearningRepository,
    SQLiteLearningRepository,
    clean_quiz_result,
)


@pytest.fixture(params=["sqlite", "postgres"])
def repo(request, tmp_path):
    if request.param == "sqlite":
        repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
        repository.initialize()
        yield repository
        return
    engine = request.getfixturevalue("pg_engine")
    user = f"gram-{uuid.uuid4().hex[:10]}"
    PostgresAuthRepository(engine).upsert_user({"sub": user, "email": f"{user}@example.test", "name": user}, set())
    user_token = USER_KEY_CTX.set(user)
    language_token = LANGUAGE_CODE_CTX.set("en")
    repository = PostgresLearningRepository(engine)
    repository.engine_for_tests = engine
    yield repository
    LANGUAGE_CODE_CTX.reset(language_token)
    USER_KEY_CTX.reset(user_token)


T0 = "2026-09-30T10:00:00+00:00"
T1 = "2026-10-02T10:00:00+00:00"


def test_completion_and_quiz_are_written_together_and_read_back(repo):
    saved = repo.record_grammar_completion("en.present_perfect", T0, {"correct": 2, "total": 3})
    assert (saved["last_quiz_correct"], saved["last_quiz_total"]) == (2, 3)
    assert saved["completed_at"].startswith("2026-09-30T10:00:00") and saved["last_quiz_at"].startswith("2026-09-30T10:00:00")
    assert saved["via"] == "id"
    assert "en.present_perfect" in repo.completed_grammar_ids()


def test_a_retake_updates_the_result_and_keeps_the_first_completion(repo):
    repo.record_grammar_completion("en.past_simple", T0, {"correct": 1, "total": 3})
    again = repo.record_grammar_completion("en.past_simple", T1, {"correct": 3, "total": 3})
    assert (again["last_quiz_correct"], again["last_quiz_total"]) == (3, 3)
    assert again["completed_at"].startswith("2026-09-30"), "completed_at is the first completion"
    assert again["last_quiz_at"].startswith("2026-10-02")


def test_a_completion_without_a_quiz_leaves_an_earlier_result_alone(repo):
    repo.record_grammar_completion("en.gerunds", T0, {"correct": 2, "total": 4})
    bare = repo.record_grammar_completion("en.gerunds", T1)
    assert (bare["last_quiz_correct"], bare["last_quiz_total"]) == (2, 4)
    first = repo.record_grammar_completion("en.infinitives", T0)
    assert first["last_quiz_correct"] is None and first["last_quiz_at"] is None


@pytest.mark.parametrize("quiz", [
    {"correct": 4, "total": 3}, {"correct": -1, "total": 3}, {"correct": 0, "total": 0},
    {"correct": 1}, {"total": 3}, {"correct": True, "total": 3}, {"correct": 1.5, "total": 3}, {},
])
def test_an_impossible_or_partial_result_is_refused_and_nothing_is_written(repo, quiz):
    with pytest.raises(ValueError):
        repo.record_grammar_completion("en.modals", T0, quiz)
    assert "en.modals" not in repo.completed_grammar_ids(), "a refused quiz must not complete the point either"


def test_the_zero_score_is_a_result_not_an_absence(repo):
    saved = repo.record_grammar_completion("en.articles", T0, {"correct": 0, "total": 5})
    assert saved["last_quiz_correct"] == 0 and saved["last_quiz_total"] == 5


def test_the_result_is_read_under_an_alias_and_nothing_is_rewritten(repo):
    """R5 completions keep their own id; the Grammar Lab point reads them through its aliases."""
    repo.set_grammar_completed("r5-present-perfect", T0)
    found = repo.get_grammar_progress("en.present_perfect", aliases=("r5-present-perfect",))
    assert found["via"] == "alias" and found["point_id"] == "r5-present-perfect"
    assert repo.get_grammar_progress("en.present_perfect") is None
    repo.record_grammar_completion("en.present_perfect", T1, {"correct": 3, "total": 3})
    own = repo.get_grammar_progress("en.present_perfect", aliases=("r5-present-perfect",))
    assert own["via"] == "id", "the point's own row wins over its alias"
    assert "r5-present-perfect" in repo.completed_grammar_ids(), "the R5 row is untouched"


def test_two_writers_at_once_leave_one_row_and_a_valid_result(repo):
    barrier = threading.Barrier(2)
    errors = []

    def write(correct):
        barrier.wait()
        try:
            repo.record_grammar_completion("en.conditionals", T0, {"correct": correct, "total": 3})
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=contextvars.copy_context().run, args=(write, n)) for n in (1, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors
    final = repo.get_grammar_progress("en.conditionals")
    assert final["last_quiz_correct"] in (1, 3) and final["last_quiz_total"] == 3


def test_the_database_itself_refuses_a_partial_or_impossible_result(repo):
    """The PostgreSQL CHECK is the last guard, independent of the Python one."""
    if not hasattr(repo, "engine_for_tests"):
        pytest.skip("SQLite cannot add a CHECK to an existing table; clean_quiz_result holds it there")
    repo.record_grammar_completion("en.check", T0)
    with pytest.raises(IntegrityError):
        with repo.engine_for_tests.begin() as connection:
            connection.execute(text("UPDATE grammar_progress SET last_quiz_correct=5, last_quiz_total=3, last_quiz_at=now() WHERE lesson_id='en.check'"))
    with pytest.raises(IntegrityError):
        with repo.engine_for_tests.begin() as connection:
            connection.execute(text("UPDATE grammar_progress SET last_quiz_correct=1 WHERE lesson_id='en.check'"))


def test_clean_quiz_result_is_the_shared_invariant():
    assert clean_quiz_result(None) is None
    assert clean_quiz_result({"correct": 0, "total": 1}) == (0, 1)
