"""Consent evidence and voice consent on the account row (D-233; migration 20261019_0036, proposed).

SQLite is the hermetic test backend: `SQLiteAuthRepository.initialize` adds the five columns, the way it adds 0018's. The
PostgreSQL proof of the same migration is `tests/test_consent_evidence_postgres.py` (skipped without
`ORENA_TEST_POSTGRES_URL`). The dormancy tests build a `users` table WITHOUT the columns, which is what a runtime that has
not applied the migration looks like.
"""
from __future__ import annotations

import ast
import asyncio
import base64
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

import auth_support
from writing_coach import account_settings, consent, speech_api
from writing_coach.core.request_context import USER_KEY_CTX
from writing_coach.persistence import consent_store, deletion_enumeration
from writing_coach.persistence.auth_repository import SQLiteAuthRepository

ROOT = Path(__file__).resolve().parents[1]
NAME = "20261019_0036_consent_evidence.py"
PROPOSED = ROOT / "migrations" / "proposed" / NAME


@pytest.fixture(autouse=True)
def _restore_account_context():
    """These tests point the account settings at their own repository; put the process-wide wiring back after each."""
    saved = (account_settings._repository, account_settings._user_key)  # noqa: SLF001
    token = USER_KEY_CTX.set(USER_KEY_CTX.get(""))
    yield
    USER_KEY_CTX.reset(token)
    account_settings._repository, account_settings._user_key = saved  # noqa: SLF001


# --- the proposal ----------------------------------------------------------------------------------------------------


def _migration():
    spec = importlib.util.spec_from_file_location("consent_0036", PROPOSED)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_migration_is_proposed_only_and_parented_on_the_head():
    assert PROPOSED.exists()
    assert not list((ROOT / "migrations" / "versions").glob("*consent*"))
    tree = ast.parse(PROPOSED.read_text(encoding="utf-8"))
    values = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Constant)
    }
    assert values["revision"] == "20261019_0036" and values["down_revision"] == "20261018_0035"
    heads = sorted(p.name for p in (ROOT / "migrations" / "versions").glob("2026*.py"))
    assert heads[-1].startswith("20261018_0035"), "0036 must be parented on the promoted head"
    assert {"upgrade", "downgrade"} <= {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_the_migration_adds_five_columns_to_a_populated_users_table_and_drops_them_again(tmp_path):
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, user_key TEXT NOT NULL)"))
        conn.execute(text("INSERT INTO users (user_key) VALUES ('a'), ('b')"))
    module = _migration()
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        module.upgrade()
    columns = {c["name"]: c for c in inspect(engine).get_columns("users")}
    assert set(consent_store.CONSENT_COLUMNS) <= set(columns)
    assert columns["voice_consent"]["nullable"] is False
    assert all(columns[name]["nullable"] for name in consent_store.CONSENT_COLUMNS if name != "voice_consent")
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT consent_version, consent_accepted_at, consent_language, voice_consent, voice_consent_at FROM users"
        )).fetchall()
    assert [tuple(r) for r in rows] == [(None, None, None, 0, None)] * 2, "existing rows: no record, voice off, no rewrite"
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        module.downgrade()
    assert set(c["name"] for c in inspect(engine).get_columns("users")) == {"id", "user_key"}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM users")).scalar() == 2


def test_the_deletion_enumeration_resets_exactly_the_five_columns():
    assert set(deletion_enumeration.CONSENT_COLUMNS_TO_RESET) == set(consent_store.CONSENT_COLUMNS)
    assert deletion_enumeration.CONSENT_COLUMNS_TO_RESET["voice_consent"] is False


# --- dormant until the columns exist ---------------------------------------------------------------------------------


@pytest.fixture
def bare(tmp_path):
    """A repository whose `users` table has no consent columns: a runtime that has not applied 0036."""
    path = tmp_path / "bare.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE users (google_sub TEXT PRIMARY KEY, email TEXT)")
    conn.execute("INSERT INTO users VALUES ('u1', 'u1@example.test')")
    conn.commit()
    conn.close()
    return SimpleNamespace(consent=consent_store.SQLiteConsentStore(path))


def test_every_read_and_write_degrades_to_no_record_without_the_columns(bare):
    store = bare.consent
    assert store.get("u1") is None
    assert store.accept("u1", "2026-10-19", "vi", only_if_unset=True) is False
    assert store.set_voice("u1", True) is False
    assert store.reset("u1") is False
    assert consent.consent_state(bare, "u1")["available"] is False
    assert consent.consent_required(bare, "u1") is False
    assert consent.record_sign_up_consent(bare, "u1", "vi") is False
    assert consent.accept_consent(bare, "u1", "vi") is False
    assert consent.set_voice_consent(bare, "u1", True) is False
    assert consent.reset_consent(bare, "u1") is False
    assert consent.public_shape(bare, "u1") == {
        "stored": False, "consent_required": False, "consent_version": "", "voice_consent": None,
    }
    assert consent.voice_consent_blocks(bare, "u1", auth_enabled=True) is False


def test_a_repository_without_a_store_is_the_same_as_absent_columns():
    assert consent.public_shape(object(), "u1")["stored"] is False
    assert consent.public_shape(None, "u1")["stored"] is False


def test_the_endpoints_answer_stored_false_and_record_nothing_without_the_columns(bare, monkeypatch):
    account_settings.configure_account_settings(bare)
    USER_KEY_CTX.set("u1")
    app = FastAPI()
    app.include_router(account_settings.router)
    client = TestClient(app)
    expected = {"stored": False, "consent_required": False, "consent_version": "", "voice_consent": None}
    assert client.get("/api/account-settings/consent").json() == expected
    assert client.post("/api/account-settings/consent", json={"language": "vi"}).json() == expected
    assert client.post("/api/account-settings/voice-consent", json={"granted": True}).json() == expected


def test_a_probe_that_fails_is_absent_not_an_error(tmp_path):
    store = consent_store.SQLiteConsentStore(tmp_path / "missing" / "nope.db")
    assert store.get("u1") is None and store.set_voice("u1", True) is False


def test_an_absent_answer_is_asked_again_later_and_a_present_one_is_kept(tmp_path):
    answers = iter([False, True])
    now = [0.0]
    presence = consent_store._Presence(lambda: next(answers), clock=lambda: now[0])
    assert presence() is False
    now[0] = consent_store.ABSENT_RECHECK_SECONDS - 1
    assert presence() is False, "not asked again within the interval"
    now[0] = consent_store.ABSENT_RECHECK_SECONDS + 1
    assert presence() is True, "a runtime that applied the migration starts recording without a restart"
    now[0] += 10_000
    assert presence() is True


# --- recording, with the columns ------------------------------------------------------------------------------------


@pytest.fixture
def repo(tmp_path):
    repository = SQLiteAuthRepository(tmp_path / "auth.db")
    repository.initialize(set())
    return repository


def _user(repo, sub="g-1"):
    return repo.upsert_user({"sub": sub, "email": f"{sub}@example.test", "name": sub}, set())


def test_upsert_says_whether_the_account_was_just_created(repo):
    assert _user(repo)["created_now"] is True
    assert _user(repo)["created_now"] is False


def test_a_new_account_records_the_version_time_and_language_once(repo, monkeypatch):
    monkeypatch.setenv("LEGAL_EFFECTIVE_DATE", "2026-10-20")
    _user(repo)
    assert consent.consent_required(repo, "g-1") is True
    assert consent.record_sign_up_consent(repo, "g-1", "vi-VN,vi;q=0.9,en;q=0.8") is True
    state = consent.consent_state(repo, "g-1")
    assert state["accepted"] and state["version"] == "2026-10-20" and state["language"] == "vi"
    assert state["accepted_at"] and state["voice"] is False
    first = state["accepted_at"]
    monkeypatch.setenv("LEGAL_EFFECTIVE_DATE", "2027-01-01")
    assert consent.record_sign_up_consent(repo, "g-1", "zh") is False, "a sign-in never overwrites a record"
    again = consent.consent_state(repo, "g-1")
    assert (again["version"], again["language"], again["accepted_at"]) == ("2026-10-20", "vi", first)
    assert consent.consent_required(repo, "g-1") is False


def test_the_version_is_unstamped_when_the_deploy_gave_no_date(monkeypatch):
    monkeypatch.delenv("LEGAL_EFFECTIVE_DATE", raising=False)
    assert consent.current_legal_version() == consent.UNSTAMPED
    assert consent.current_legal_version({"LEGAL_EFFECTIVE_DATE": "12/10/2026"}) == consent.UNSTAMPED
    assert consent.current_legal_version({"LEGAL_EFFECTIVE_DATE": "2026-10-12"}) == "2026-10-12"
    assert [consent.normalize_language(v) for v in ("vi", "zh-CN", "fr", "", None, "EN-GB")] == [
        "vi", "zh", "en", "en", "en", "en",
    ]


def _client(repo, key):
    account_settings.configure_account_settings(repo)
    USER_KEY_CTX.set(key)
    app = FastAPI()
    app.include_router(account_settings.router)
    return TestClient(app)


def test_an_existing_account_without_a_record_is_asked_once_and_the_answer_is_stored(repo, monkeypatch):
    monkeypatch.setenv("LEGAL_EFFECTIVE_DATE", "2026-10-20")
    _user(repo)
    client = _client(repo, "g-1")
    before = client.get("/api/account-settings/consent").json()
    assert before == {"stored": True, "consent_required": True, "consent_version": "", "voice_consent": False}
    after = client.post("/api/account-settings/consent", json={"language": "zh"}).json()
    assert after == {"stored": True, "consent_required": False, "consent_version": "2026-10-20", "voice_consent": False}
    assert consent.consent_state(repo, "g-1")["language"] == "zh"


def test_the_voice_answer_is_stored_both_ways_with_its_time(repo):
    _user(repo)
    client = _client(repo, "g-1")
    on = client.post("/api/account-settings/voice-consent", json={"granted": True}).json()
    assert on["voice_consent"] is True and consent.consent_state(repo, "g-1")["voice_at"]
    assert client.post("/api/account-settings/voice-consent", json={"granted": False}).json()["voice_consent"] is False
    assert client.post("/api/account-settings/voice-consent", json={}).status_code == 422


def test_deletion_resets_every_consent_column(repo):
    _user(repo)
    consent.accept_consent(repo, "g-1", "vi")
    consent.set_voice_consent(repo, "g-1", True)
    assert consent.reset_consent(repo, "g-1") is True
    state = consent.consent_state(repo, "g-1")
    assert (state["accepted"], state["version"], state["language"], state["voice"], state["voice_at"]) == (
        False, "", "", False, "",
    )
    conn = sqlite3.connect(repo.path)
    row = conn.execute(
        "SELECT consent_version, consent_accepted_at, consent_language, voice_consent, voice_consent_at "
        "FROM users WHERE google_sub = 'g-1'"
    ).fetchone()
    assert tuple(row) == (None, None, None, 0, None)


# --- the voice gate on the speech routes ----------------------------------------------------------------------------


def _speech_client(repo, key, monkeypatch, *, auth):
    account_settings.configure_account_settings(repo)
    monkeypatch.setattr(account_settings, "_auth_enabled", lambda: auth)
    USER_KEY_CTX.set(key)
    app = FastAPI()
    app.include_router(speech_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _post_audio(client, path, **form):
    return client.post(path, files={"file": ("take.webm", b"x", "audio/webm")}, data=form)


@pytest.mark.parametrize("path,form", [
    ("/api/speech/transcribe", {"language": "en"}),
    ("/api/speech/pronunciation", {"language": "en", "reference_text": "hello"}),
])
def test_speech_audio_routes_refuse_403_until_the_learner_allows_recording(repo, monkeypatch, path, form):
    _user(repo)
    client = _speech_client(repo, "g-1", monkeypatch, auth=True)
    refused = _post_audio(client, path, **form)
    assert refused.status_code == 403
    assert "voice_consent_required" in refused.text
    consent.set_voice_consent(repo, "g-1", True)
    assert _post_audio(client, path, **form).status_code != 403, "once allowed the request reaches the route"
    consent.set_voice_consent(repo, "g-1", False)
    assert _post_audio(client, path, **form).status_code == 403, "turning it off applies at once"


def test_the_gate_enforces_a_stored_refusal_never_a_missing_store(repo, bare, monkeypatch):
    _user(repo)
    assert consent.voice_consent_blocks(repo, "g-1", auth_enabled=True) is True
    assert consent.voice_consent_blocks(repo, "g-1", auth_enabled=False) is False, "local development has no sign-in"
    assert consent.voice_consent_blocks(repo, "nobody", auth_enabled=True) is False, "no account row"
    assert consent.voice_consent_blocks(bare, "u1", auth_enabled=True) is False, "columns absent"
    client = _speech_client(bare, "u1", monkeypatch, auth=True)
    assert _post_audio(client, "/api/speech/transcribe", language="en").status_code != 403


# --- sign-in and the bootstrap --------------------------------------------------------------------------------------


def _session_cookie(**values: str) -> str:
    encoded = base64.b64encode(json.dumps(values).encode("utf-8"))
    return TimestampSigner(auth_support.SESSION_SECRET or "local-single-user-mode").sign(encoded).decode("utf-8")


def _sign_in_world(repo, monkeypatch, sub):
    import app as app_module

    monkeypatch.setenv("LEGAL_EFFECTIVE_DATE", "2026-10-20")
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "_auth_repository", repo)
    monkeypatch.setattr(auth_support, "maybe_claim_legacy_data", lambda *_a, **_k: False)
    info = {"sub": sub, "email": f"{sub}@example.test", "name": "New", "email_verified": True, "nonce": "n"}
    fake_flow = SimpleNamespace(
        fetch_token=lambda code: None, credentials=SimpleNamespace(id_token="tok"), code_verifier="v",
        authorization_url=lambda **_k: ("https://accounts.example.test/auth", None),
    )
    monkeypatch.setattr(auth_support, "google_flow", lambda code_verifier=None: fake_flow)
    monkeypatch.setattr(auth_support.google_id_token, "verify_oauth2_token", lambda *_a, **_k: info)
    monkeypatch.setattr(auth_support, "_move_to_sign_in_host", lambda _request: None)

    async def sign_in(start_query="", accept_language=""):
        """The start (`/auth/google`) and the callback, with the cookie the start set carried to the callback."""
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            started = await client.get(f"/auth/google{start_query}")
            assert started.status_code == 302
            session = json.loads(base64.b64decode(started.cookies["writing_coach_session"].split(".")[0] + "=="))
            client.cookies.set(
                "writing_coach_session",
                _session_cookie(**{**session, "oauth_state": "s", "oauth_nonce": "n"}),
            )
            return await client.get("/auth/google/callback?state=s&code=c", headers={"accept-language": accept_language})

    return sign_in


def test_the_account_step_sign_in_of_a_new_account_records_consent_with_the_language_it_carried(repo, monkeypatch):
    sign_in = _sign_in_world(repo, monkeypatch, "g-new")
    first = asyncio.run(sign_in("?next=%2F&account_step=1&lang=vi", accept_language="zh"))
    assert first.status_code == 302
    state = consent.consent_state(repo, "g-new")
    assert state["accepted"] and state["version"] == "2026-10-20"
    assert state["language"] == "vi", "the interface language the Account step carried, not the browser's"
    asyncio.run(sign_in("?account_step=1&lang=zh"))
    assert consent.consent_state(repo, "g-new")["language"] == "vi", "a returning sign-in records nothing"


def test_the_browser_language_is_only_the_fallback_when_the_flag_carries_none(repo, monkeypatch):
    sign_in = _sign_in_world(repo, monkeypatch, "g-fb")
    asyncio.run(sign_in("?account_step=1", accept_language="vi-VN,vi;q=0.9"))
    assert consent.consent_state(repo, "g-fb")["language"] == "vi"


@pytest.mark.parametrize("query", ["", "?next=%2F", "?account_step=0&lang=vi", "?account_step=1&lang=vi&native_redirect_uri=orena%3A%2F%2Fauth%2Fcallback&native_code_challenge=" + "a" * 43])
def test_a_sign_in_not_started_at_the_account_step_records_nothing_and_the_sheet_is_due(repo, monkeypatch, query):
    sign_in = _sign_in_world(repo, monkeypatch, "g-direct")
    asyncio.run(sign_in(query))
    assert repo.get_user("g-direct") is not None, "the account was created"
    assert consent.consent_state(repo, "g-direct")["accepted"] is False
    assert consent.consent_required(repo, "g-direct") is True, "the one-time sheet asks instead"


def test_the_bootstrap_carries_the_consent_flag_for_an_account_with_no_record(repo, monkeypatch):
    import app as app_module

    _user(repo, "g-boot")
    monkeypatch.setattr(auth_support, "AUTH_ENABLED", True)
    monkeypatch.setattr(auth_support, "_auth_repository", repo)
    monkeypatch.setattr(account_settings, "_repository", repo)

    async def fetch():
        transport = httpx.ASGITransport(app=app_module.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.cookies.set("writing_coach_session", _session_cookie(user_sub="g-boot", language="en"))
            return (await client.get("/api/session/bootstrap")).json()

    body = asyncio.run(fetch())
    assert body["consent"] == {"stored": True, "consent_required": True, "consent_version": "", "voice_consent": False}
    consent.accept_consent(repo, "g-boot", "en")
    assert asyncio.run(fetch())["consent"]["consent_required"] is False


# --- the gate fails closed on an unreadable record; logs stay quiet ----------------------------------------------------


def test_the_voice_gate_fails_closed_when_the_columns_are_present_but_the_read_fails(repo, monkeypatch):
    _user(repo)
    consent.set_voice_consent(repo, "g-1", True)
    client = _speech_client(repo, "g-1", monkeypatch, auth=True)
    assert _post_audio(client, "/api/speech/transcribe", language="en").status_code != 403

    def broken(*_a, **_k):
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(repo.consent, "_connect", broken)
    assert repo.consent.available() is True, "the columns are known present"
    with pytest.raises(consent_store.ConsentUnreadable):
        consent.voice_consent_blocks(repo, "g-1", auth_enabled=True)
    refused = _post_audio(client, "/api/speech/transcribe", language="en")
    assert refused.status_code == 503 and "consent_unavailable" in refused.text, "an unreadable answer is not a yes"
    # everything else degrades to "no record": the bootstrap and the settings read never fail on it
    assert consent.public_shape(repo, "g-1")["stored"] is False
    assert consent.consent_required(repo, "g-1") is False


def test_a_persistent_fault_logs_its_traceback_once_then_one_line(repo, monkeypatch, caplog):
    _user(repo)
    assert repo.consent.available() is True
    monkeypatch.setattr(repo.consent, "_connect", lambda: (_ for _ in ()).throw(sqlite3.OperationalError("boom")))
    with caplog.at_level("WARNING", logger=consent_store.log.name):
        for _ in range(3):
            assert consent.consent_state(repo, "g-1")["available"] is False
    with_traceback = [r for r in caplog.records if r.exc_info]
    assert len(with_traceback) == 1, "the traceback is logged once"
    assert len(caplog.records) == 3
