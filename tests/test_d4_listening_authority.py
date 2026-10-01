"""D4 slice 2: the server is authoritative for a stored Dictation score (D-103.2, D-104 H-14) and
listening/shadowing progress checks the asset's language (I16).

The rule (`listening_progress_policy.merge_progress`) is pure and runs everywhere. The route and the
real PostgreSQL repository run when `ORENA_TEST_POSTGRES_URL` names a throwaway database at the head
(the SQLite repository refuses listening progress by design).
"""
from __future__ import annotations

import contextvars
import threading
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from writing_coach import listening_api
from writing_coach.core.request_context import LANGUAGE_CODE_CTX, USER_KEY_CTX
from writing_coach.listening_catalog import catalog_lessons
from writing_coach.listening_progress_policy import merge_progress
from writing_coach.media_library_store import OWNER_FIELD, MediaLibraryEntry, owner_token
from writing_coach.persistence.auth_repository import PostgresAuthRepository
from writing_coach.persistence.specialized_repository import PostgresSpecializedLearningRepository


# --- the rule, pure --------------------------------------------------------------------------


def _score(percent, exact=False):
    return {"accuracy_percent": percent, "exact": exact}


def test_a_client_or_absent_row_is_superseded_by_the_computed_score_not_kept_by_max():
    row = {"best_accuracy_percent": 100, "best_exact": True, "checked_attempt_count": 3, "score_source": "client"}
    merged = merge_progress(row, {"checked_attempt_count": 9, "best_accuracy_percent": 100}, _score(40))
    assert merged["best_accuracy_percent"] == 40 and merged["best_exact"] is False
    assert merged["score_source"] == "server"
    fresh = merge_progress(None, {"checked_attempt_count": 1}, _score(70))
    assert fresh["best_accuracy_percent"] == 70 and fresh["score_source"] == "server"


def test_a_server_row_keeps_the_best_and_a_worse_answer_never_lowers_it():
    row = {"best_accuracy_percent": 90, "best_exact": True, "checked_attempt_count": 2, "score_source": "server"}
    worse = merge_progress(row, {"checked_attempt_count": 3}, _score(50))
    assert worse["best_accuracy_percent"] == 90 and worse["best_exact"] is True
    better = merge_progress(row, {"checked_attempt_count": 3}, _score(95))
    assert better["best_accuracy_percent"] == 95 and better["best_exact"] is True, "exact is stored or computed"


def test_the_count_is_never_lowered_and_rises_by_at_most_one_per_write():
    row = {"best_accuracy_percent": 50, "best_exact": False, "checked_attempt_count": 4, "score_source": "server"}
    assert merge_progress(row, {"checked_attempt_count": 1}, _score(10))["checked_attempt_count"] == 4
    assert merge_progress(row, {"checked_attempt_count": 5}, _score(10))["checked_attempt_count"] == 5
    assert merge_progress(row, {"checked_attempt_count": 900}, _score(10))["checked_attempt_count"] == 5
    assert merge_progress(None, {"checked_attempt_count": 900}, _score(10))["checked_attempt_count"] == 1


def test_a_write_without_a_score_changes_nothing_the_client_claimed():
    row = {"best_accuracy_percent": 60, "best_exact": False, "checked_attempt_count": 2, "score_source": "client"}
    merged = merge_progress(row, {"best_accuracy_percent": 100, "best_exact": True, "checked_attempt_count": 99}, None)
    assert merged == {"best_accuracy_percent": 60, "best_exact": False, "checked_attempt_count": 2, "score_source": "client"}
    empty = merge_progress(None, {"best_accuracy_percent": 100, "checked_attempt_count": 5}, None)
    assert empty["best_accuracy_percent"] is None and empty["checked_attempt_count"] == 0
    assert empty["score_source"] == "client"


# --- the route on the real PostgreSQL repository ---------------------------------------------


def _lesson(language):
    for lesson in catalog_lessons(language=language):
        for item in lesson.source.segments:
            if int(item["start_ms"]) >= lesson.excerpt_start_ms and int(item["end_ms"]) <= lesson.excerpt_end_ms:
                return lesson.source.source_media_id, item
    pytest.skip(f"no {language} lesson in the catalogue")


class MemoryMediaStore:
    def __init__(self, entries):
        self.entries = {entry.media_id: entry for entry in entries}

    def get(self, media_id):
        return self.entries.get(media_id)


def _own_media(media_id, language, text_, owner):
    # Personal media is owned by the account that uploaded it (39b9f12); an owner-less entry is the local account's only.
    return MediaLibraryEntry(
        media_id=media_id, media_type="audio", provider="upload", provider_media_id=media_id,
        canonical_url="", playback={"provider": "upload", "kind": "audio", "url": "/x"}, title="Mine",
        thumbnail={"kind": "none", "ref": ""}, duration_ms=5000, language=language, level="", creator="",
        source={"provider": "upload", "type": "audio", "provenance_url": "", "license": "own",
                "review_status": "own", "imported_by": "learner", OWNER_FIELD: owner_token(owner)},
        library="personal", created_at="2026-09-30T00:00:00+00:00",
        lesson={"payload": {"asset": {"asset_id": media_id, "source_language": language},
                            "transcript": {"segments": [{"segment_id": "s1", "order": 0, "start_ms": 0,
                                                         "end_ms": 4000, "original_text": text_}]}}},
    )


@pytest.fixture
def api(pg_engine):
    auth = PostgresAuthRepository(pg_engine)
    repository = PostgresSpecializedLearningRepository(pg_engine)
    user = f"dict-{uuid.uuid4().hex[:12]}"
    auth.upsert_user({"sub": user, "email": f"{user}@example.test", "name": user}, set())
    user_token = USER_KEY_CTX.set(user)
    language_token = LANGUAGE_CODE_CTX.set("en")
    listening_api.configure_listening_progress(repository)
    listening_api.configure_listening_media_library(MemoryMediaStore([_own_media("upload-abc", "en", "Hello there my friend", user)]))
    app = FastAPI()
    app.include_router(listening_api.router)
    yield TestClient(app), repository, pg_engine, user
    LANGUAGE_CODE_CTX.reset(language_token)
    USER_KEY_CTX.reset(user_token)
    listening_api.configure_listening_progress(None)
    listening_api.configure_listening_media_library(None)


def _save(client, asset, segment, **fields):
    body = {"asset_id": asset, "segment_id": segment["segment_id"] if isinstance(segment, dict) else segment, **fields}
    return client.post("/api/listening/progress", json=body)


def test_a_forged_score_is_replaced_by_the_computed_one(api):
    client, *_ = api
    asset, segment = _lesson("en")
    response = _save(client, asset, segment, presentation="checked", last_answer="completely unrelated words here",
                     checked_attempt_count=1, best_accuracy_percent=100, best_exact=True)
    item = response.json()["item"]
    assert response.status_code == 200
    assert item["best_accuracy_percent"] < 100 and item["best_exact"] is False and item["score_source"] == "server"


def test_the_best_survives_a_worse_answer_and_rises_with_a_better_one(api):
    client, *_ = api
    asset, segment = _lesson("en")
    target = str(segment.get("spoken_text") or segment["original_text"])
    exact = _save(client, asset, segment, presentation="checked", last_answer=target, checked_attempt_count=1).json()["item"]
    assert exact["best_accuracy_percent"] == 100 and exact["best_exact"] is True
    worse = _save(client, asset, segment, presentation="checked", last_answer="nope", checked_attempt_count=2,
                  best_accuracy_percent=0).json()["item"]
    assert worse["best_accuracy_percent"] == 100 and worse["best_exact"] is True
    assert worse["checked_attempt_count"] == 2 and worse["last_answer"] == "nope"
    lowered = _save(client, asset, segment, presentation="checked", last_answer="nope again", checked_attempt_count=1).json()["item"]
    assert lowered["checked_attempt_count"] == 2, "the count is never lowered"
    jumped = _save(client, asset, segment, presentation="checked", last_answer="nope", checked_attempt_count=500).json()["item"]
    assert jumped["checked_attempt_count"] == 3, "at most one more per write"


def test_a_revealed_or_prompt_write_changes_no_score(api):
    client, *_ = api
    asset, segment = _lesson("en")
    target = str(segment.get("spoken_text") or segment["original_text"])
    _save(client, asset, segment, presentation="checked", last_answer=target, checked_attempt_count=1)
    revealed = _save(client, asset, segment, presentation="revealed", best_accuracy_percent=0, best_exact=False,
                     checked_attempt_count=0).json()["item"]
    assert revealed["revealed"] is True
    assert (revealed["best_accuracy_percent"], revealed["best_exact"], revealed["checked_attempt_count"]) == (100, True, 1)
    prompt = _save(client, asset, segment, best_accuracy_percent=3).json()["item"]
    assert prompt["best_accuracy_percent"] == 100


def test_an_old_client_number_is_superseded_by_the_first_verified_check(api):
    client, repository, engine, user = api
    asset, segment = _lesson("en")
    _save(client, asset, segment, presentation="prompt")  # creates the row
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE listening_progress SET best_accuracy_percent=100, best_exact=true, checked_attempt_count=5,"
            " score_source='client' WHERE asset_id=:a AND segment_id=:s AND user_id=(SELECT id FROM users WHERE user_key=:u)"),
            {"a": asset, "s": segment["segment_id"], "u": user})
    listed = client.get("/api/listening/progress", params={"asset_id": asset}).json()["items"]
    assert listed[0]["score_source"] == "client" and listed[0]["best_accuracy_percent"] == 100
    superseded = _save(client, asset, segment, presentation="checked", last_answer="totally different", checked_attempt_count=6).json()["item"]
    assert superseded["score_source"] == "server" and superseded["best_accuracy_percent"] < 100
    assert superseded["checked_attempt_count"] == 6


def test_refusals_are_422_with_the_evaluators_codes(api):
    client, *_ = api
    asset, segment = _lesson("en")
    assert _save(client, asset, segment, presentation="checked", last_answer="   ").status_code == 200, "no answer is not a score"
    too_large = _save(client, asset, segment, presentation="checked", last_answer="\U0001F600" * 1001)
    assert too_large.status_code == 422 and too_large.json()["detail"]["category"] == "answer_too_large"
    punctuation = _save(client, asset, segment, presentation="checked", last_answer="... !!!")
    assert punctuation.status_code == 422 and punctuation.json()["detail"]["category"] == "answer_empty"


def test_an_unserved_pair_is_404_and_a_foreign_language_is_422_and_nothing_is_stored(api):
    client, repository, engine, user = api
    asset, segment = _lesson("en")
    zh_asset, zh_segment = _lesson("zh")
    missing = _save(client, "no-such-asset", "s1", presentation="prompt")
    assert missing.status_code == 404 and missing.json()["detail"]["category"] == "asset_not_found"
    wrong_segment = _save(client, asset, "no-such-segment", presentation="prompt")
    assert wrong_segment.status_code == 404
    foreign = _save(client, zh_asset, zh_segment, presentation="checked", last_answer="你好")
    assert foreign.status_code == 422 and foreign.json()["detail"]["category"] == "asset_language_mismatch"
    shadow = client.post("/api/listening/shadowing-progress", json={"asset_id": zh_asset, "segment_id": zh_segment["segment_id"], "completed_rounds": 1})
    assert shadow.status_code == 422
    unknown = client.post("/api/listening/shadowing-progress", json={"asset_id": "nope", "segment_id": "s", "completed_rounds": 1})
    assert unknown.status_code == 404
    ok = client.post("/api/listening/shadowing-progress", json={"asset_id": asset, "segment_id": segment["segment_id"], "completed_rounds": 1})
    assert ok.status_code == 200
    with engine.connect() as connection:
        stored = connection.execute(text(
            "SELECT count(*) FROM listening_progress WHERE asset_id IN (:a,:b)"
            " AND user_id=(SELECT id FROM users WHERE user_key=:u)"), {"a": zh_asset, "b": "no-such-asset", "u": user}).scalar()
    assert stored == 0


def test_a_chinese_scope_grades_chinese_and_refuses_english_assets(api):
    client, *_ = api
    LANGUAGE_CODE_CTX.set("zh")
    zh_asset, zh_segment = _lesson("zh")
    target = str(zh_segment.get("spoken_text") or zh_segment["original_text"])
    item = _save(client, zh_asset, zh_segment, presentation="checked", last_answer=target, checked_attempt_count=1).json()["item"]
    assert item["best_accuracy_percent"] == 100 and item["language"] == "zh"
    en_asset, en_segment = _lesson("en")
    assert _save(client, en_asset, en_segment, presentation="prompt").status_code == 422


def test_the_learners_own_media_resolves_by_its_id(api):
    client, *_ = api
    ok = _save(client, "upload-abc", "s1", presentation="checked", last_answer="hello there my friend", checked_attempt_count=1)
    assert ok.status_code == 200 and ok.json()["item"]["best_accuracy_percent"] == 100
    assert _save(client, "upload-abc", "other", presentation="prompt").status_code == 404


def test_two_simultaneous_checks_are_both_kept_under_the_row_lock(api):
    client, repository, engine, user = api
    asset, segment = _lesson("en")
    _save(client, asset, segment, presentation="prompt")
    results = []
    barrier = threading.Barrier(2)

    def check(answer):
        barrier.wait()
        results.append(_save(client, asset, segment, presentation="checked", last_answer=answer, checked_attempt_count=1).status_code)

    target = str(segment.get("spoken_text") or segment["original_text"])
    threads = [threading.Thread(target=contextvars.copy_context().run, args=(check, answer)) for answer in ("wrong", target)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [200, 200]
    final = client.get("/api/listening/progress", params={"asset_id": asset}).json()["items"][0]
    assert final["best_accuracy_percent"] == 100, "the exact answer wins whichever committed last"


def test_two_simultaneous_first_checks_of_a_segment_both_succeed_and_keep_the_best(api):
    """Implementation review P2-1: nothing exists to lock on a first write, so the row is created before it is locked."""
    client, repository, engine, user = api
    asset, segment = _lesson("en")
    target = str(segment.get("spoken_text") or segment["original_text"])
    results = []
    barrier = threading.Barrier(4)

    def check(answer):
        barrier.wait()
        results.append(_save(client, asset, segment, presentation="checked", last_answer=answer, checked_attempt_count=1).status_code)

    threads = [threading.Thread(target=contextvars.copy_context().run, args=(check, answer))
               for answer in ("wrong words", target, "still wrong", "nope")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [200, 200, 200, 200], results
    final = client.get("/api/listening/progress", params={"asset_id": asset}).json()["items"]
    assert len(final) == 1 and final[0]["best_accuracy_percent"] == 100 and final[0]["score_source"] == "server"
    assert final[0]["checked_attempt_count"] >= 1
