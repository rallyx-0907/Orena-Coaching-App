"""D4 slice 5: refresh an old Chinese review under the current evaluator contract, keeping the old one
as immutable history (I19, D-103.7, D-104 H-15).

Real repositories on both backends (SQLite always, PostgreSQL when ORENA_TEST_POSTGRES_URL is set) and
the real `/api/essays/{id}/review/refresh` route. Only the network provider is faked.
"""
from __future__ import annotations

import contextvars
import json
import sqlite3
import threading
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import app as app_module
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from writing_coach.persistence.auth_repository import PostgresAuthRepository
from writing_coach.persistence.learning_repository import PostgresLearningRepository, SQLiteLearningRepository
from writing_coach.persistence.specialized_repository import (
    PostgresSpecializedLearningRepository,
    SQLiteSpecializedLearningRepository,
)
from writing_coach.writing_review_identity import review_identity

V26 = "writing-evaluation-v2.6"
V27 = "writing-evaluation-v2.7"
ZH_TEXT = "我今天去了学校，我们学习了很多新的汉字，老师说我们写得很好。"


def _review(index: int = 1, **over: Any) -> dict[str, Any]:
    return {
        "grammar": 61.0, "vocabulary": 62.0, "coherence": 63.0, "task_achievement": 64.0, "naturalness": 65.0,
        "cefr_estimate": "HSK3", "summary_vi": f"Refreshed #{index}", "strengths_vi": ["Clear."],
        "strength_evidence": [], "priorities_vi": ["Watch particles."], "errors": [],
        "schema_version": "writing-evaluation-v2", "_ai_provider": "test", "_ai_model": "model", **over,
    }


class Stack:
    def __init__(self, name, learning, specialized, engine=None):
        self.name, self.learning, self.specialized, self.engine = name, learning, specialized, engine


@pytest.fixture(params=["sqlite", "postgres"])
def stack(request, tmp_path, monkeypatch):
    if request.param == "sqlite":
        learning = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
        learning.initialize()
        specialized = SQLiteSpecializedLearningRepository(learning.connect)
        specialized.initialize()
        built = Stack("sqlite", learning, specialized)
    else:
        engine = request.getfixturevalue("pg_engine")
        PostgresAuthRepository(engine).upsert_user({"sub": "legacy", "email": "local@localhost.invalid", "name": "L"}, set())
        built = Stack("postgres", PostgresLearningRepository(engine), PostgresSpecializedLearningRepository(engine), engine)
        built.learning.initialize = lambda **kwargs: None  # the local-mode request hook expects the SQLite shape
        built.specialized.initialize = lambda **kwargs: None
    # Direct repository calls run in the Chinese scope, where these essays live (requests get theirs from the session).
    scope = LANGUAGE_CODE_CTX.set("zh")
    request.addfinalizer(lambda: LANGUAGE_CODE_CTX.reset(scope))
    monkeypatch.setattr(app_module, "_learning_repository", built.learning)
    monkeypatch.setattr(app_module, "_specialized_learning_repository", built.specialized)
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", False)
    app_module._review_in_flight.clear()
    return built


def seed(stack, *, learning="zh", support="vi", contract=V26, text_=ZH_TEXT, identity=True, practice=None, links=None):
    """A stored review written under an older contract (the row a refresh would replace)."""
    values = {
        "created_at": "2026-09-20T10:00:00+00:00", "prompt": "Write about your day", "text": text_ + uuid.uuid4().hex[:6],
        "word_count": 30, "target_cefr": "HSK3", "grammar": 40.0, "vocabulary": 41.0, "coherence": 42.0,
        "task_achievement": 43.0, "naturalness": 44.0, "overall": 42.0, "cefr_estimate": "HSK2", "evaluator": "old:eval",
        "summary_vi": "Old review", "strengths_json": json.dumps(["Old strength"]), "strength_evidence_json": "[]",
        "priorities_json": json.dumps(["Old priority"]), "errors_json": json.dumps([{"category": "particles", "fragment": "了"}]),
        "series_id": None, "revision_no": 1, "parent_id": None,
        "practice_context": practice, "grammar_links": links or [{"grammar_id": "zh.le"}], "review_identity": None,
    }
    if identity:
        values["review_identity"] = review_identity(
            text=values["text"], learning_language=learning, support_language=support,
            target_level="HSK3", prompt=values["prompt"], contract_version=contract,
        )
    token = LANGUAGE_CODE_CTX.set(learning.split("-")[0])  # PostgreSQL scopes an essay by its language
    try:
        created = stack.learning.create_essay(values)
    finally:
        LANGUAGE_CODE_CTX.reset(token)
    return int(created["id"]), values


@pytest.fixture
def client(stack, monkeypatch):
    calls: list[dict[str, Any]] = []
    behaviour = {"result": _review, "raise": None}

    def fake(payload, *, support=None):
        calls.append({"text": payload.text, "support": support})
        if behaviour["raise"]:
            raise behaviour["raise"]
        return behaviour["result"](len(calls))

    monkeypatch.setattr(app_module, "evaluate_with_ai", fake)
    monkeypatch.setattr(app_module, "get_learner_profile", lambda *a, **k: {"support_language": "en", "native_language": "en"})
    test_client = TestClient(app_module.app)
    test_client.__enter__()
    test_client.post("/api/platform/language", json={"language": "zh"})
    test_client.calls, test_client.behaviour = calls, behaviour
    yield test_client
    test_client.__exit__(None, None, None)


# --- the route -----------------------------------------------------------------------------


def test_an_affected_stale_review_is_refreshed_once_and_the_old_one_is_kept(client, stack):
    essay_id, values = seed(stack, learning="zh", support="vi", practice={"kind": "task"}, links=[{"grammar_id": "zh.le"}])
    before = client.get(f"/api/essays/{essay_id}").json()
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.status_code == 200 and answer.json()["status"] == "refreshed"
    assert len(client.calls) == 1
    assert client.calls[0]["support"][0] == "vi", "the STORED support language, not the current profile's (en)"
    after = client.get(f"/api/essays/{essay_id}").json()
    assert after["summary_vi"] == "Refreshed #1" and after["evaluator"] == "test:model"
    assert (after["series_id"], after["revision_no"]) == (before["series_id"], before["revision_no"]), "no learner revision is created"
    assert after["module_data"]["review"]["contract"] == V27
    assert after["module_data"]["review"]["fingerprint"] != before["module_data"]["review"]["fingerprint"]
    for key in ("practice", "grammar_links"):
        assert after["module_data"][key] == before["module_data"][key], f"{key} must survive a refresh"
    history = client.get(f"/api/essays/{essay_id}/review/history").json()["items"]
    assert len(history) == 1
    kept = history[0]
    assert kept["reason"] == "evaluator_refresh" and kept["prior_fingerprint"] == before["module_data"]["review"]["fingerprint"]
    assert kept["prior_contract"] == V26 and kept["replaced_by_fingerprint"] == after["module_data"]["review"]["fingerprint"]
    assert kept["review"]["summary_vi"] == "Old review" and kept["review"]["strengths"] == ["Old strength"]
    assert kept["review"]["overall"] == 42.0 and kept["review"]["grammar_links"] == [{"grammar_id": "zh.le"}]
    again = client.post(f"/api/essays/{essay_id}/review/refresh").json()
    assert again["status"] == "current" and len(client.calls) == 1, "a repeat is free"
    assert len(client.get(f"/api/essays/{essay_id}/review/history").json()["items"]) == 1


@pytest.mark.parametrize("learning,support", [("en", "vi"), ("zh", "zh"), ("zh", "zh-CN"), ("en", "en")])
def test_an_unaffected_pair_is_current_with_no_provider_call(client, stack, learning, support):
    client.post("/api/platform/language", json={"language": learning})
    essay_id, _ = seed(stack, learning=learning, support=support, contract=V26)
    assert client.post(f"/api/essays/{essay_id}/review/refresh").json()["status"] == "current"
    assert client.calls == []


def test_a_review_written_under_v27_for_an_unaffected_pair_is_never_touched_by_a_refresh(client, stack):
    client.post("/api/platform/language", json={"language": "en"})
    essay_id, _ = seed(stack, learning="en", support="vi", contract=V27)
    assert client.post(f"/api/essays/{essay_id}/review/refresh").json()["status"] == "current"
    assert client.calls == [] and client.get(f"/api/essays/{essay_id}/review/history").json()["items"] == []


def test_chinese_with_a_cjk_support_language_other_than_chinese_is_affected(client, stack):
    essay_id, _ = seed(stack, learning="zh", support="ja")
    if app_module.support_language("ja") is None:
        pytest.skip("Japanese is not an available support language in this build")
    assert client.post(f"/api/essays/{essay_id}/review/refresh").json()["status"] == "refreshed"
    assert client.calls[0]["support"][0] == "ja"


def test_an_essay_with_no_stored_identity_is_not_refreshed(client, stack):
    essay_id, _ = seed(stack, identity=False)
    assert client.post(f"/api/essays/{essay_id}/review/refresh").json()["status"] == "unverifiable"
    assert client.calls == []
    assert client.get(f"/api/essays/{essay_id}").json()["summary_vi"] == "Old review"


def test_a_provider_failure_writes_nothing_and_can_be_retried(client, stack):
    from fastapi import HTTPException

    essay_id, _ = seed(stack)
    client.behaviour["raise"] = HTTPException(503, "down")
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.status_code == 200 and answer.json()["status"] == "unavailable"
    assert client.get(f"/api/essays/{essay_id}").json()["summary_vi"] == "Old review"
    assert client.get(f"/api/essays/{essay_id}/review/history").json()["items"] == []
    client.behaviour["raise"] = None
    assert client.post(f"/api/essays/{essay_id}/review/refresh").json()["status"] == "refreshed"


def test_the_local_fallback_can_never_replace_a_real_review(client, stack, monkeypatch):
    """Even with ALLOW_FALLBACK on for ordinary reviews, the refresh runs provider-only."""
    from writing_coach.ai.base import AIProviderUnavailable

    essay_id, _ = seed(stack)
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", True)
    client.behaviour["raise"] = AIProviderUnavailable("down")
    answer = client.post(f"/api/essays/{essay_id}/review/refresh")
    assert answer.json()["status"] == "unavailable"
    detail = client.get(f"/api/essays/{essay_id}").json()
    assert detail["evaluator"] == "old:eval" and detail["summary_vi"] == "Old review"
    assert client.get(f"/api/essays/{essay_id}/review/history").json()["items"] == []


def test_the_stored_pair_is_used_after_the_learner_changes_their_support_language(client, stack, monkeypatch):
    essay_id, _ = seed(stack, learning="zh", support="vi")
    monkeypatch.setattr(app_module, "get_learner_profile", lambda *a, **k: {"support_language": "en", "native_language": "en"})
    assert client.post(f"/api/essays/{essay_id}/review/refresh").json()["status"] == "refreshed"
    stored = client.get(f"/api/essays/{essay_id}").json()["module_data"]["review"]
    assert (stored["learning_language"], stored["support_language"]) == ("zh", "vi")


def test_two_simultaneous_refreshes_of_one_essay_give_one_provider_call_and_one_history_row(client, stack):
    essay_id, _ = seed(stack)
    results = []
    barrier = threading.Barrier(2)

    def go():
        barrier.wait()
        results.append(client.post(f"/api/essays/{essay_id}/review/refresh").json()["status"])

    threads = [threading.Thread(target=contextvars.copy_context().run, args=(go,)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == ["current", "refreshed"], results
    assert len(client.calls) == 1
    assert len(client.get(f"/api/essays/{essay_id}/review/history").json()["items"]) == 1


def test_an_unknown_essay_is_404(client, stack):
    assert client.post("/api/essays/987654/review/refresh").status_code == 404
    assert client.get("/api/essays/987654/review/history").status_code == 404


# --- the repository ------------------------------------------------------------------------


def _new_review():
    return {"grammar": 70.0, "vocabulary": 71.0, "coherence": 72.0, "task_achievement": 73.0, "naturalness": 74.0,
            "overall": 72.0, "cefr_estimate": "HSK4", "evaluator": "new:eval", "summary_vi": "New", "strengths": ["s"],
            "strength_evidence": [], "priorities": ["p"], "errors": []}


def _identity_for(values, contract=V27):
    return review_identity(text=values["text"], learning_language="zh", support_language="vi", target_level="HSK3",
                           prompt=values["prompt"], contract_version=contract)


def test_the_row_lock_method_returns_already_current_when_the_fingerprint_moved(stack):
    essay_id, values = seed(stack)
    prior = values["review_identity"]["fingerprint"]
    stale = stack.specialized.refresh_essay_review(essay_id, "not-the-stored-fingerprint", _new_review(), _identity_for(values), "2026-09-30T10:00:00+00:00")
    assert stale["status"] == "already_current"
    ok = stack.specialized.refresh_essay_review(essay_id, prior, _new_review(), _identity_for(values), "2026-09-30T10:00:00+00:00")
    assert ok["status"] == "refreshed" and ok["history_id"]
    again = stack.specialized.refresh_essay_review(essay_id, prior, _new_review(), _identity_for(values), "2026-09-30T10:00:01+00:00")
    assert again["status"] == "already_current"
    assert len(stack.specialized.list_essay_review_history(essay_id)) == 1


def test_a_concurrent_linguistic_cache_write_and_a_refresh_both_survive(stack):
    essay_id, values = seed(stack)
    prior = values["review_identity"]["fingerprint"]
    outcomes = []
    barrier = threading.Barrier(2)

    def refresh():
        barrier.wait()
        outcomes.append(stack.specialized.refresh_essay_review(essay_id, prior, _new_review(), _identity_for(values), "2026-09-30T10:00:00+00:00")["status"])

    def cache():
        barrier.wait()
        outcomes.append(stack.specialized.merge_essay_module_data(essay_id, "linguistic_cache", {"hash": "h"}))

    threads = [threading.Thread(target=contextvars.copy_context().run, args=(fn,)) for fn in (refresh, cache)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert "refreshed" in outcomes and True in outcomes
    bag = json.loads(stack.specialized.get_linguistic_essay(essay_id)["module_data_json"])
    assert bag["linguistic_cache"] == {"hash": "h"} and bag["review"]["contract"] == V27
    assert bag["grammar_links"] == [{"grammar_id": "zh.le"}]


def test_history_is_reachable_only_by_essay_id_and_the_repository_cannot_change_it(stack):
    names = {name for name in dir(stack.specialized) if "history" in name}
    assert names == {"list_essay_review_history"}, names
    assert not any(name.startswith(("update", "delete", "remove", "set")) for name in names)


def test_another_account_and_another_language_read_no_history(stack):
    if stack.name != "postgres":
        pytest.skip("SQLite is one database file per account and language; scope is the file")
    essay_id, values = seed(stack)
    stack.specialized.refresh_essay_review(essay_id, values["review_identity"]["fingerprint"], _new_review(), _identity_for(values), "2026-09-30T10:00:00+00:00")
    assert len(stack.specialized.list_essay_review_history(essay_id)) == 1
    token = USER_KEY_CTX.set("someone-else")
    try:
        assert stack.specialized.list_essay_review_history(essay_id) == []
        assert stack.specialized.refresh_essay_review(essay_id, "x", _new_review(), _identity_for(values), "2026-09-30T10:00:00+00:00")["status"] == "not_found"
    finally:
        USER_KEY_CTX.reset(token)
    language = LANGUAGE_CODE_CTX.set("en")
    try:
        assert stack.specialized.list_essay_review_history(essay_id) == []
    finally:
        LANGUAGE_CODE_CTX.reset(language)


def test_deleting_the_essay_deletes_its_history(stack):
    essay_id, values = seed(stack)
    stack.specialized.refresh_essay_review(essay_id, values["review_identity"]["fingerprint"], _new_review(), _identity_for(values), "2026-09-30T10:00:00+00:00")
    assert stack.learning.delete_series_for_essay(essay_id) is True
    if stack.name == "sqlite":
        with sqlite3.connect(stack.learning.path()) as connection:
            assert connection.execute("SELECT count(*) FROM essay_review_history").fetchone()[0] == 0
    else:
        assert stack.specialized.list_essay_review_history(essay_id) == []
        with stack.engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM essay_review_history h LEFT JOIN essays e ON e.id=h.essay_id WHERE e.id IS NULL")).scalar() == 0


def test_the_database_trigger_refuses_an_update_of_history(stack):
    if stack.name != "postgres":
        pytest.skip("the immutability trigger is PostgreSQL only; SQLite exposes insert and read")
    essay_id, values = seed(stack)
    stack.specialized.refresh_essay_review(essay_id, values["review_identity"]["fingerprint"], _new_review(), _identity_for(values), "2026-09-30T10:00:00+00:00")
    with pytest.raises(DBAPIError):
        with stack.engine.begin() as connection:
            connection.execute(text("UPDATE essay_review_history SET reason='tampered' WHERE prior_fingerprint=:p"), {"p": values["review_identity"]["fingerprint"]})


# --- the prompt reference travels with the essay (I5, D-103.6) -------------------------------------


def test_the_prompt_a_piece_answers_is_recorded_as_a_reference_beside_the_review(client, stack):
    posted = client.post("/api/evaluate", json={
        "prompt": "Write about your day", "text": ZH_TEXT + "。今天天气很好。", "learning_language": "zh",
        "prompt_ref": {"source": "prompt-bank", "id": "day-01"}})
    assert posted.status_code == 200, posted.text
    detail = client.get(f"/api/essays/{posted.json()['id']}").json()
    assert detail["module_data"]["prompt_ref"] == {"source": "prompt-bank", "id": "day-01"}
    assert "review" in detail["module_data"], "the review identity is written beside it, unchanged"
    free = client.post("/api/evaluate", json={"prompt": "", "text": ZH_TEXT + "。我很开心。", "learning_language": "zh"})
    assert "prompt_ref" not in client.get(f"/api/essays/{free.json()['id']}").json()["module_data"], "free writing sends no reference"
    bad = client.post("/api/evaluate", json={"prompt": "", "text": ZH_TEXT, "prompt_ref": {"source": "Bad Source", "id": "x"}})
    assert bad.status_code == 422
