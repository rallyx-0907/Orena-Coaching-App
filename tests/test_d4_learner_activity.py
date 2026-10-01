"""D4 slice 7: a real streak, derived, no table; and no unmeasured number (I14; D-104 H-5, D-103.4).

The counting is pure and runs everywhere. The route and the records it reads run on the real
repositories: essays on SQLite and PostgreSQL, speaking attempts and the `since` window on PostgreSQL.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from writing_coach import learner_activity
from writing_coach.persistence.models import Base

UTC_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)  # a Wednesday


def at(day: str, hour: int = 12) -> datetime:
    return datetime.fromisoformat(day).replace(hour=hour, tzinfo=UTC)


# --- the counting, pure ---------------------------------------------------------------------------


def test_there_is_no_streak_table():
    assert not [name for name in Base.metadata.tables if "streak" in name or "learning_day" in name]


def test_consecutive_days_ending_today_or_yesterday_make_a_streak_and_a_gap_breaks_it():
    zone = learner_activity.resolve_timezone("UTC")
    today = date(2026, 9, 30)
    days = learner_activity.active_days([at("2026-09-30"), at("2026-09-29"), at("2026-09-28"), at("2026-09-25")], zone)
    assert learner_activity.streak_length(days, today) == 3
    yesterday = learner_activity.active_days([at("2026-09-29"), at("2026-09-28")], zone)
    assert learner_activity.streak_length(yesterday, today) == 2, "today not yet active does not break it"
    stale = learner_activity.active_days([at("2026-09-27"), at("2026-09-26")], zone)
    assert learner_activity.streak_length(stale, today) == 0
    assert learner_activity.streak_length(set(), today) == 0


def test_a_day_is_the_learners_own_calendar_day_not_utc():
    instant = datetime(2026, 9, 29, 18, 30, tzinfo=UTC)  # 01:30 on the 30th in Ho Chi Minh City
    hcm = learner_activity.active_days([instant], learner_activity.resolve_timezone("Asia/Ho_Chi_Minh"))
    utc = learner_activity.active_days([instant], learner_activity.resolve_timezone("UTC"))
    assert hcm == {date(2026, 9, 30)} and utc == {date(2026, 9, 29)}
    result_hcm = learner_activity.compute_activity({"essays": [instant]}, now=UTC_NOW, tz="Asia/Ho_Chi_Minh")
    result_utc = learner_activity.compute_activity({"essays": [instant]}, now=UTC_NOW, tz="UTC")
    assert result_hcm["streak"] == {"days": 1, "active_today": True}
    assert result_utc["streak"] == {"days": 1, "active_today": False}


def test_a_late_night_row_can_be_yesterday_in_one_zone_and_today_in_another():
    now = datetime(2026, 9, 30, 20, 0, tzinfo=UTC)  # the 1st of October 03:00 in Ho Chi Minh City
    instants = {"essays": [datetime(2026, 9, 30, 8, 0, tzinfo=UTC)]}
    assert learner_activity.compute_activity(instants, now=now, tz="UTC")["streak"]["active_today"] is True
    assert learner_activity.compute_activity(instants, now=now, tz="Asia/Ho_Chi_Minh")["streak"] == {"days": 1, "active_today": False}, (
        "yesterday still counts as a streak day; the boundary moved with the zone")


def test_the_week_is_the_iso_week_and_the_goal_is_the_persisted_target_or_absent():
    sources = {"essays": [at("2026-09-28"), at("2026-09-30")], "speaking_attempts": [at("2026-09-29")], "reading_attempts": [at("2026-09-21")]}
    result = learner_activity.compute_activity(sources, now=UTC_NOW, tz="UTC", weekly_goal_days=4)
    week = result["week"]
    assert week["start"] == "2026-09-28" and week["done_days"] == 3 and week["goal_days"] == 4
    assert [day["active"] for day in week["days"]] == [True, True, True, False, False, False, False]
    assert [day["future"] for day in week["days"]] == [False, False, False, True, True, True, True]
    assert "goal_days" not in learner_activity.compute_activity(sources, now=UTC_NOW, tz="UTC")["week"]
    assert result["recent_days"] == ["2026-09-21", "2026-09-28", "2026-09-29", "2026-09-30"]


def test_only_completed_server_records_count_and_the_others_say_why_they_do_not():
    result = learner_activity.compute_activity({"essays": []}, now=UTC_NOW, tz="UTC")
    assert result["sources"]["counted"] == ["essays", "speaking_attempts", "reading_attempts"]
    assert set(result["sources"]["pending"]) >= {"listening_dictation", "shadowing", "vocabulary_review"}
    assert all(reason == "no_per_event_timestamp" for name, reason in result["sources"]["pending"].items() if name in {"listening_dictation", "shadowing", "vocabulary_review"})
    rogue = learner_activity.compute_activity({"vocabulary_review": [at("2026-09-30")]}, now=UTC_NOW, tz="UTC")
    assert rogue["streak"]["days"] == 0, "a source that is not registered adds nothing"


def test_an_unmeasured_value_is_absent_never_zero():
    result = learner_activity.compute_activity({}, now=UTC_NOW, tz="UTC")
    flat = repr(result)
    for unmeasured in ("minutes", "daily_goal", "achievement", "trend", "percent", "xp", "level"):
        assert unmeasured not in flat, unmeasured


def test_an_unknown_timezone_is_refused():
    with pytest.raises(ValueError):
        learner_activity.resolve_timezone("Mars/Olympus")


# --- the route on the real repositories -------------------------------------------------------------


def _client(backend, user):
    backend.use(user, "en")
    learner_activity.configure_learner_activity(lambda since: backend.profile_repo(user, "en").activity_timestamps(since))
    app = FastAPI()
    app.include_router(learner_activity.router)
    return TestClient(app)


def _write_essay(backend, user, created_at: datetime, text_="I went to school."):
    backend.use(user, "en")
    values = {
        "created_at": created_at.isoformat(timespec="seconds"), "prompt": "", "text": text_ + uuid.uuid4().hex[:6], "word_count": 4,
        "target_cefr": "", "grammar": 50.0, "vocabulary": 50.0, "coherence": 50.0, "task_achievement": 50.0, "naturalness": 50.0,
        "overall": 50.0, "cefr_estimate": "B1", "evaluator": "t:m", "summary_vi": "s", "strengths_json": "[]",
        "strength_evidence_json": "[]", "priorities_json": "[]", "errors_json": "[]", "series_id": None, "revision_no": 1,
        "parent_id": None, "practice_context": None, "grammar_links": [], "review_identity": None,
    }
    backend.learning_repo(user, "en").create_essay(values)


def test_the_route_counts_real_essays_by_the_learners_day_and_a_visit_adds_nothing(backend):
    user = backend.new_user()
    client = _client(backend, user)
    now = datetime.now(UTC)
    for days_ago in (0, 1, 2, 5):
        _write_essay(backend, user, now - timedelta(days=days_ago))
    first = client.get("/api/learner-activity", params={"tz": "UTC", "days": 28}).json()
    assert first["streak"]["days"] == 3 and first["streak"]["active_today"] is True
    again = client.get("/api/learner-activity", params={"tz": "UTC"}).json()
    assert again["streak"] == first["streak"] and again["recent_days"] == first["recent_days"], "opening the page changes nothing"
    assert first["week"]["done_days"] >= 1


def test_the_route_reads_the_weekly_goal_from_the_account_and_refuses_a_bad_timezone(backend):
    user = backend.new_user()
    client = _client(backend, user)
    no_goal = client.get("/api/learner-activity").json()["week"]
    assert "goal_days" not in no_goal
    backend.auth.update_account_settings(user, {"weekly_goal_days": 3}, "")
    assert client.get("/api/learner-activity", params={"tz": "Asia/Ho_Chi_Minh"}).json()["week"]["goal_days"] == 3
    assert client.get("/api/learner-activity", params={"tz": "Nope/Nope"}).status_code == 422
    assert client.get("/api/learner-activity", params={"days": 3}).status_code == 422
    assert client.get("/api/learner-activity", params={"days": 91}).status_code == 422


def test_two_accounts_and_two_languages_do_not_share_days(backend):
    one, two = backend.new_user(), backend.new_user()
    _write_essay(backend, one, datetime.now(UTC))
    assert _client(backend, one).get("/api/learner-activity").json()["streak"]["days"] == 1
    assert _client(backend, two).get("/api/learner-activity").json()["streak"]["days"] == 0


def test_speaking_attempts_count_and_the_since_window_is_kept_by_the_server(backend):
    if backend.name != "postgres":
        pytest.skip("Speaking attempts are durable only on the PostgreSQL runtime")
    from writing_coach import speech_api

    user = backend.new_user()
    client = _client(backend, user)
    repo = backend.profile_repo(user, "en")
    now = datetime.now(UTC)
    for take, when in (("new", now - timedelta(minutes=5)), ("old", now - timedelta(days=2))):
        repo.create_speaking_attempt_record({
            "take_id": f"{take}-{uuid.uuid4().hex[:6]}", "asset_id": "free", "segment_id": "invite-1", "reference_text": "",
            "transcript_text": "hello", "dimensions": {}, "provenance": {}, "evidence": {}, "created_at": when.isoformat()})
    assert client.get("/api/learner-activity").json()["streak"]["days"] >= 1
    speech_api.configure_speaking_attempt_repository(repo)
    app = FastAPI()
    app.include_router(speech_api.router)
    window = TestClient(app)
    assert window.get("/api/speech/attempts", params={"limit": 20}).status_code == 200
    since = (now - timedelta(hours=1)).isoformat()
    recent = window.get("/api/speech/attempts", params={"since": since}).json()["items"]
    assert len(recent) == 1 and recent[0]["transcript_text"] == "hello"
    assert window.get("/api/speech/attempts", params={"since": "yesterday"}).status_code == 422
    clamped = window.get("/api/speech/attempts", params={"since": "2001-01-01T00:00:00Z"}).json()["items"]
    assert len(clamped) == 2, "an old since is clamped to seven days, never further"
    future = window.get("/api/speech/attempts", params={"since": (now + timedelta(days=3)).isoformat()}).json()["items"]
    assert future == [], "a future since is a window with nothing in it"
    speech_api.configure_speaking_attempt_repository(None)
