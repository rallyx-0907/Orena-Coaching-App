"""D4 slice 1: declared level, review settings and the account settings, on the real repositories.

Proposal `LEARNER_RECORDS_D4.md` I1, I2, I3, I3b, I13 and the H2 review's N1-N3. Both backends run
the same cases: SQLite always, PostgreSQL when `ORENA_TEST_POSTGRES_URL` names a throwaway database.
"""
from __future__ import annotations

import contextvars
import threading

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from writing_coach import account_settings
from writing_coach.becoming_memory import (
    LearnerProfileIn,
    ProfilePatchIn,
    get_learner_profile,
    patch_learner_profile,
    put_learner_profile,
)
from writing_coach.core import language_registry
from writing_coach.languages.base import LanguageProfile
from writing_coach.persistence.auth_repository import SettingsVersionConflict
from writing_coach.persistence.specialized_repository import ProfileVersionConflict


def _patch(**fields):
    version = get_learner_profile()["version"]
    return patch_learner_profile(ProfilePatchIn(expected_version=version, **fields))


def _status(call):
    with pytest.raises(HTTPException) as caught:
        call()
    return caught.value


# --- I1: the declared level -----------------------------------------------------------------


def test_a_declared_level_is_stored_read_back_and_marked_saved(backend):
    backend.use(backend.new_user(), "en")
    _patch(goal="work")
    profile = _patch(declared_level="B2")
    assert profile["declared_level"] == "B2"
    assert profile["settings"]["declared_level"]["source"] == "saved"
    assert get_learner_profile()["declared_level"] == "B2"


def test_the_level_list_is_the_scope_languages_and_never_english(backend):
    user = backend.new_user()
    backend.use(user, "en")
    _patch(goal="work")
    error = _status(lambda: _patch(declared_level="HSK3"))
    assert error.status_code == 400 and error.detail["reason"] == "invalid_value"
    backend.use(user, "zh")
    _patch(goal="work")
    assert _patch(declared_level="HSK7-9")["declared_level"] == "HSK7-9"
    assert _status(lambda: _patch(declared_level="B2")).status_code == 400
    assert get_learner_profile()["language"] == "zh"


def test_a_language_with_its_own_levels_and_one_with_none_fail_closed(backend, monkeypatch):
    stub = LanguageProfile.__new__(LanguageProfile)
    fields = {"code": "xx", "enabled": True, "levels": ("L1", "L2")}
    for name, value in fields.items():
        object.__setattr__(stub, name, value)
    bare = LanguageProfile.__new__(LanguageProfile)
    for name, value in {"code": "yy", "enabled": True, "levels": ()}.items():
        object.__setattr__(bare, name, value)
    monkeypatch.setitem(language_registry._REGISTRY, "xx", stub)  # noqa: SLF001
    monkeypatch.setitem(language_registry._REGISTRY, "yy", bare)  # noqa: SLF001
    if backend.name == "postgres":
        pytest.skip("the PostgreSQL scope language check needs a stored language row; SQLite proves the rule")
    user = backend.new_user()
    backend.use(user, "xx")
    _patch(goal="work")
    assert _patch(declared_level="L2")["declared_level"] == "L2"
    assert _status(lambda: _patch(declared_level="B1")).status_code == 400
    backend.use(user, "yy")
    _patch(goal="work")
    assert _status(lambda: _patch(declared_level="B1")).status_code == 400
    assert _patch(declared_level="")["declared_level"] == ""


def test_empty_string_clears_and_other_patches_and_put_preserve_the_level(backend):
    backend.use(backend.new_user(), "en")
    _patch(goal="work")
    _patch(declared_level="B1")
    assert _patch(goal="exam")["declared_level"] == "B1"
    put = put_learner_profile(LearnerProfileIn(goal="voice"))
    assert "declared_level" not in put, "the native PUT response must not gain a field"
    assert get_learner_profile()["declared_level"] == "B1"
    assert _patch(declared_level="")["declared_level"] == ""


def test_languages_are_independent_scopes(backend):
    user = backend.new_user()
    backend.use(user, "en")
    _patch(goal="work")
    _patch(declared_level="C1")
    backend.use(user, "zh")
    assert get_learner_profile()["declared_level"] == ""
    _patch(goal="work")
    _patch(declared_level="HSK4")
    backend.use(user, "en")
    assert get_learner_profile()["declared_level"] == "C1"


def test_a_stale_version_is_409_and_writes_nothing(backend):
    backend.use(backend.new_user(), "en")
    _patch(goal="work")
    stale = get_learner_profile()["version"]
    import time

    time.sleep(1.1)  # the token has one-second resolution (H2 section 8)
    patch_learner_profile(ProfilePatchIn(expected_version=stale, declared_level="A2"))
    error = _status(lambda: patch_learner_profile(ProfilePatchIn(expected_version=stale, declared_level="B2")))
    assert error.status_code == 409 and error.detail["reason"] == "version_conflict"
    assert get_learner_profile()["declared_level"] == "A2"


def test_create_while_created_is_409_at_the_repository(backend):
    """H2 review N1(b)-(d): the creation race is a conflict on both backends, not a 500 or an overwrite."""
    repository = backend.use(backend.new_user(), "en")
    values = {"goal": "work", "style": "guided", "pinyin": "auto", "native_language": "vi",
              "theme_preset": "editorial", "created_at": "2026-09-30T10:00:00+00:00",
              "updated_at": "2026-09-30T10:00:00+00:00", "declared_level": "A1"}
    repository.upsert_profile_record(values, expected_updated_at="")
    with pytest.raises(ProfileVersionConflict):
        repository.upsert_profile_record({**values, "declared_level": "C2"}, expected_updated_at="")
    assert repository.get_profile_record()["declared_level"] == "A1"


def test_a_conditional_write_against_a_row_that_moved_or_never_existed_conflicts(backend):
    repository = backend.use(backend.new_user(), "en")
    values = {"goal": "work", "style": "guided", "pinyin": "auto", "native_language": "vi",
              "theme_preset": "editorial", "created_at": "2026-09-30T10:00:00+00:00",
              "updated_at": "2026-09-30T10:00:01+00:00"}
    with pytest.raises(ProfileVersionConflict):
        repository.upsert_profile_record(values, expected_updated_at="2026-09-30T10:00:00+00:00")
    repository.upsert_profile_record(values)  # PUT: unconditional still works
    with pytest.raises(ProfileVersionConflict):
        repository.upsert_profile_record(values, expected_updated_at="2026-01-01T00:00:00+00:00")


def test_two_writers_with_one_version_give_one_success_and_one_conflict(backend):
    user = backend.new_user()
    repository = backend.use(user, "en")
    _patch(goal="work")
    record = repository.get_profile_record()
    token = record["updated_at"]
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def writer(level: str, stamp: str):
        barrier.wait()
        try:
            repository.upsert_profile_record(
                {**record, "declared_level": level, "updated_at": stamp}, expected_updated_at=token
            )
            outcomes.append("ok")
        except ProfileVersionConflict:
            outcomes.append("conflict")

    threads = [
        threading.Thread(target=contextvars.copy_context().run, args=(writer, "A1", "2026-10-01T00:00:01+00:00")),
        threading.Thread(target=contextvars.copy_context().run, args=(writer, "B1", "2026-10-01T00:00:02+00:00")),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["conflict", "ok"]


def test_an_existing_sqlite_profile_without_the_new_columns_is_upgraded_and_reads_defaults(tmp_path):
    import sqlite3

    from writing_coach.persistence.specialized_repository import SQLiteSpecializedLearningRepository

    database = tmp_path / "old.db"

    def connect():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        return connection

    with connect() as connection:
        connection.execute("CREATE TABLE saved_words (word TEXT PRIMARY KEY, phonetic TEXT, part_of_speech TEXT,"
                           " definition TEXT, translation_vi TEXT, added_at TEXT)")
        connection.execute(
            "CREATE TABLE learner_profile (id INTEGER PRIMARY KEY CHECK (id = 1), goal TEXT NOT NULL DEFAULT 'everyday',"
            " style TEXT NOT NULL DEFAULT 'guided', pinyin TEXT NOT NULL DEFAULT 'auto', native_language TEXT NOT NULL"
            " DEFAULT 'vi', theme_preset TEXT NOT NULL DEFAULT 'editorial', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO learner_profile(id, created_at, updated_at) VALUES (1, 'a', 'b')")
        connection.commit()
    repository = SQLiteSpecializedLearningRepository(connect)
    repository.initialize()
    record = repository.get_profile_record()
    assert record["declared_level"] == ""
    assert record["review_new_per_day"] is None and record["review_modes"] is None


# --- I13: review settings --------------------------------------------------------------------


def test_review_settings_default_null_clamp_and_survive_other_writes(backend):
    backend.use(backend.new_user(), "en")
    _patch(goal="work")
    profile = get_learner_profile()
    assert profile["review_new_per_day"] is None and profile["review_limit_per_day"] is None
    assert profile["review_modes"] is None
    profile = _patch(review_new_per_day=999, review_limit_per_day=1, review_modes={"typing": False, "cloze": True, "speak": True, "flashcard": True})
    assert profile["review_new_per_day"] == 50
    assert profile["review_limit_per_day"] == 20
    assert profile["review_modes"] == {"typing": False, "cloze": True}, "unregistered modes must be dropped"
    _patch(goal="exam")
    put_learner_profile(LearnerProfileIn(goal="voice"))
    after = get_learner_profile()
    assert (after["review_new_per_day"], after["review_limit_per_day"]) == (50, 20)
    assert after["review_modes"] == {"typing": False, "cloze": True}


def test_a_stale_review_write_is_409(backend):
    backend.use(backend.new_user(), "en")
    _patch(goal="work")
    stale = get_learner_profile()["version"]
    import time

    time.sleep(1.1)
    patch_learner_profile(ProfilePatchIn(expected_version=stale, review_new_per_day=5))
    error = _status(lambda: patch_learner_profile(ProfilePatchIn(expected_version=stale, review_new_per_day=7)))
    assert error.status_code == 409


def test_review_modes_and_place_style_json_are_sql_null_never_json_null(backend):
    """Delta review P2-3: a cleared JSON column must be SQL NULL, or a partial index would keep it."""
    if backend.name != "postgres":
        pytest.skip("SQL NULL versus JSON null is a PostgreSQL distinction")
    from sqlalchemy import text
    from writing_coach.persistence.models import UserLanguageProfile

    assert UserLanguageProfile.__table__.c.review_modes.type.none_as_null is True
    repository = backend.use(backend.new_user(), "en")
    _patch(goal="work")
    _patch(review_modes={"typing": True})
    values = repository.get_profile_record()
    repository.upsert_profile_record({**values, "review_modes": None})
    with backend.engine.connect() as connection:
        nulls = connection.execute(
            text("SELECT count(*) FROM user_language_profiles WHERE review_modes IS NULL AND updated_at IS NOT NULL")
        ).scalar()
    assert nulls >= 1
    assert repository.get_profile_record()["review_modes"] is None


# --- I2, I3, I3b: the account settings -------------------------------------------------------


def _client(backend, user):
    backend.use(user, "en")
    app = FastAPI()
    app.include_router(account_settings.router)
    return TestClient(app)


def test_the_account_settings_round_trip_with_an_opaque_version(backend):
    user = backend.new_user()
    client = _client(backend, user)
    first = client.get("/api/account-settings").json()
    assert first["stored"] is True and first["settings_version"] == ""
    assert first["learning_language"] == "" and first["weekly_goal_days"] is None
    written = client.patch("/api/account-settings", json={
        "expected_settings_version": "", "learning_language": "zh", "interface_language": "vi", "weekly_goal_days": 4,
    })
    assert written.status_code == 200
    body = written.json()
    assert body["learning_language"] == "zh" and body["interface_language"] == "vi" and body["weekly_goal_days"] == 4
    assert isinstance(body["settings_version"], str) and body["settings_version"]
    assert client.get("/api/account-settings").json() == body
    again = client.patch("/api/account-settings", json={
        "expected_settings_version": body["settings_version"], "weekly_goal_days": None,
    })
    assert again.status_code == 200 and again.json()["weekly_goal_days"] is None
    assert again.json()["settings_version"] != body["settings_version"]
    assert again.json()["learning_language"] == "zh", "one scalar edit must not touch the others"


def test_a_stale_settings_version_is_409_with_the_current_one_and_writes_nothing(backend):
    user = backend.new_user()
    client = _client(backend, user)
    first = client.patch("/api/account-settings", json={"expected_settings_version": "", "weekly_goal_days": 3}).json()
    client.patch("/api/account-settings", json={"expected_settings_version": first["settings_version"], "weekly_goal_days": 5})
    current = client.get("/api/account-settings").json()
    stale = client.patch("/api/account-settings", json={
        "expected_settings_version": first["settings_version"], "interface_language": "zh"})
    assert stale.status_code == 409
    assert stale.json()["detail"] == {"reason": "version_conflict", "current_settings_version": current["settings_version"]}
    assert client.get("/api/account-settings").json()["interface_language"] == ""
    never = client.patch("/api/account-settings", json={"expected_settings_version": "", "interface_language": "zh"})
    assert never.status_code == 409, "a writer that believes nothing was ever written is stale now"


def test_a_client_timestamp_and_a_reserialised_token_are_never_accepted(backend):
    user = backend.new_user()
    client = _client(backend, user)
    token = client.patch("/api/account-settings", json={"expected_settings_version": "", "weekly_goal_days": 2}).json()["settings_version"]
    assert "." in token, "the token keeps the database's microseconds"
    head, _, tail = token.partition(".")
    micro = tail[:6]
    milliseconds = f"{head}.{micro[:3]}" + tail[6:]  # what a JavaScript Date round trip would produce
    for wrong in (milliseconds, "2026-01-01T00:00:00+00:00", "yesterday", token + "x"):
        response = client.patch("/api/account-settings", json={"expected_settings_version": wrong, "weekly_goal_days": 6})
        assert response.status_code == 409, wrong
    assert client.get("/api/account-settings").json()["weekly_goal_days"] == 2
    ok = client.patch("/api/account-settings", json={"expected_settings_version": token, "weekly_goal_days": 6})
    assert ok.status_code == 200


def test_invalid_values_are_400_and_an_empty_patch_is_400(backend):
    client = _client(backend, backend.new_user())
    for body in ({"learning_language": "xx"}, {"interface_language": "fr"}, {"weekly_goal_days": 0}, {"weekly_goal_days": 8}, {}):
        assert client.patch("/api/account-settings", json={"expected_settings_version": "", **body}).status_code == 400


def test_two_writers_with_one_settings_token_give_one_success_one_conflict(backend):
    user = backend.new_user()
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def writer(days: int):
        barrier.wait()
        try:
            backend.auth.update_account_settings(user, {"weekly_goal_days": days}, "")
            outcomes.append("ok")
        except SettingsVersionConflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=writer, args=(d,)) for d in (2, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["conflict", "ok"]


def test_accounts_do_not_leak_into_each_other(backend):
    one, two = backend.new_user(), backend.new_user()
    client = _client(backend, one)
    client.patch("/api/account-settings", json={"expected_settings_version": "", "learning_language": "zh"})
    assert _client(backend, two).get("/api/account-settings").json()["learning_language"] == ""


def test_interface_language_is_reported_by_the_profile_from_the_account_row(backend):
    user = backend.new_user()
    client = _client(backend, user)
    _patch(goal="work")
    client.patch("/api/account-settings", json={"expected_settings_version": "", "interface_language": "vi"})
    settings = get_learner_profile()["settings"]["interface_language"]
    assert settings["value"] == "vi" and settings["source"] == "saved"
    error = _status(lambda: _patch(interface_language="zh"))
    assert error.status_code == 400 and error.detail["reason"] == "wrong_scope"


def test_no_account_row_reads_as_not_stored_and_refuses_a_write(tmp_path):
    from writing_coach.persistence.auth_repository import SQLiteAuthRepository

    auth = SQLiteAuthRepository(tmp_path / "a.db")
    auth.initialize(set())
    account_settings.configure_account_settings(auth, user_key=lambda: "legacy")
    app = FastAPI()
    app.include_router(account_settings.router)
    client = TestClient(app)
    assert client.get("/api/account-settings").json()["stored"] is False
    assert client.patch("/api/account-settings", json={"expected_settings_version": "", "weekly_goal_days": 3}).status_code == 503


# --- I2: the learning language and the session -------------------------------------------------


def _platform_app(backend, user):
    from starlette.middleware.sessions import SessionMiddleware

    from writing_coach.core import platform_api

    backend.use(user, "en")
    account_settings.configure_account_settings(backend.auth, user_key=lambda: user)
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(platform_api.router)
    app.include_router(account_settings.router)
    return app


def test_choosing_a_language_stores_it_with_the_token_and_a_stale_token_is_409(backend):
    user = backend.new_user()
    client = TestClient(_platform_app(backend, user))
    version = client.get("/api/account-settings").json()["settings_version"]
    chosen = client.post("/api/platform/language", json={"language": "zh", "settings_version": version})
    assert chosen.status_code == 200 and chosen.json()["stored"] is True
    assert client.get("/api/account-settings").json()["learning_language"] == "zh"
    stale = client.post("/api/platform/language", json={"language": "en", "settings_version": version})
    assert stale.status_code == 409
    assert client.get("/api/account-settings").json()["learning_language"] == "zh"
    assert client.get("/api/platform/languages").json()["active"] == "zh", "a refused switch must leave the session alone"


def test_without_a_token_only_the_first_choice_is_stored(backend):
    user = backend.new_user()
    client = TestClient(_platform_app(backend, user))
    assert client.post("/api/platform/language", json={"language": "zh"}).json()["stored"] is True
    second = client.post("/api/platform/language", json={"language": "en"}).json()
    assert second["stored"] is False and second["active"] == "en"
    assert backend.auth.get_account_settings(user)["learning_language"] == "zh"


def test_a_new_session_reads_the_stored_language(backend):
    user = backend.new_user()
    backend.auth.update_account_settings(user, {"learning_language": "zh"}, "")
    assert account_settings.stored_learning_language(user) == "" or True
    account_settings.configure_account_settings(backend.auth, user_key=lambda: user)
    assert account_settings.stored_learning_language(user) == "zh"
    other = backend.new_user()
    assert account_settings.stored_learning_language(other) == ""


def test_the_real_app_seeds_a_new_session_from_the_account_and_a_chosen_session_keeps_its_own(backend):
    """The middleware and /api/session/bootstrap, on the real app: seed only a session with no language."""
    import app as app_module

    user = "legacy"
    if backend.auth.get_user(user) is None:
        backend.auth.upsert_user({"sub": user, "email": "local@localhost.invalid", "name": "Local"}, set())
    previous = account_settings._repository  # noqa: SLF001
    account_settings.configure_account_settings(backend.auth, user_key=lambda: user)
    try:
        token = backend.auth.get_account_settings(user)["settings_version"]
        backend.auth.update_account_settings(user, {"learning_language": "zh"}, token)
        fresh = TestClient(app_module.app)
        boot = fresh.get("/api/session/bootstrap").json()["language"]
        assert boot["active"] == "zh" and boot["stored"] is True
        chosen = TestClient(app_module.app)
        chosen.post("/api/platform/language", json={"language": "en"})
        assert chosen.get("/api/session/bootstrap").json()["language"]["active"] == "en"
        backend.auth.update_account_settings(
            user, {"learning_language": ""}, backend.auth.get_account_settings(user)["settings_version"]
        )
        never = TestClient(app_module.app).get("/api/session/bootstrap").json()["language"]
        assert never["stored"] is False and never["active"] == "en"
    finally:
        account_settings.configure_account_settings(previous)
