"""D-16R `languages.target` against real PostgreSQL: the ownership query over the real tables, the account row lock,
the plan and catalogue reads, the two routes, and the Plan & usage read.

Skips unless `ORENA_TEST_POSTGRES_URL` names a THROWAWAY database (the `pg_engine` fixture upgrades it to head). CI has
no PostgreSQL service, so these run locally; `tests/test_language_limit.py` proves the same rules hermetically.

Only the language count is enforced here (`ORENA_QUOTA_METERS=languages.target`); the app itself is the two real routers
(`platform_api`, `account_settings`) over the real `PostgresAuthRepository`, the real `PostgresProductRepository` for the
plan, and the real catalogue reads.
"""
from __future__ import annotations

import concurrent.futures
import os
import threading
import time
import uuid
from datetime import UTC, datetime

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402

from writing_coach import account_settings  # noqa: E402
from writing_coach.core import language_registry, platform_api  # noqa: E402
from writing_coach.languages.base import LanguageProfile  # noqa: E402
from writing_coach.persistence.auth_repository import PostgresAuthRepository  # noqa: E402
from writing_coach.persistence.ids import stable_uuid  # noqa: E402
from writing_coach.persistence.incarnation_repository import PostgresIncarnationRepository  # noqa: E402
from writing_coach.persistence.language_ownership import (  # noqa: E402
    PostgresLanguageOwnership,
    language_scoped_tables,
    owned_languages,
)
from writing_coach.persistence.models import GrammarProgress, UserLanguageProfile  # noqa: E402
from writing_coach.persistence.product_repository import PostgresProductRepository  # noqa: E402
from writing_coach.persistence.quota_repository import PostgresQuotaRepository  # noqa: E402
from writing_coach.product import catalog, language_limit, quota  # noqa: E402
from writing_coach.product.catalog import configure_plan_store  # noqa: E402
from writing_coach.product.service import ProductService  # noqa: E402

pytestmark = pytest.mark.skipif(not os.getenv("ORENA_TEST_POSTGRES_URL"),
                                reason="ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


class World:
    """One account on the real PostgreSQL repositories, with `languages.target` enforced."""

    def __init__(self, engine, key, *, env=None):
        self.engine = engine
        self.key = key
        self.auth = PostgresAuthRepository(engine)
        self.products = PostgresProductRepository(engine)
        self.service = ProductService(self.products)
        self.incarnations = PostgresIncarnationRepository(engine)
        self.user_id = stable_uuid("user", key)
        quota.configure_quota(
            repository=PostgresQuotaRepository(engine), incarnations=self.incarnations,
            plan_for=self.service.plan_for_user, settings=None,
            env={quota.FLAG: "on", quota.METERS_FLAG: "languages.target"} if env is None else env,
        )
        self.service.usage = quota.usage_for
        language_limit.configure(PostgresLanguageOwnership(engine))
        account_settings.configure_account_settings(self.auth, user_key=lambda: self.key)
        app = FastAPI()
        app.add_middleware(SessionMiddleware, secret_key="test-secret")
        app.include_router(platform_api.router)
        app.include_router(account_settings.router)

        @app.get("/_active")
        def active(request: Request):
            return {"active": request.session.get("language")}

        self.app = app

    def client(self):
        return TestClient(self.app)

    def token(self, client):
        return client.get("/api/account-settings").json()["settings_version"]

    def post(self, client, language, *, token=True):
        body = {"language": language}
        if token:
            body["settings_version"] = self.token(client)
        return client.post("/api/platform/language", json=body)

    def plan(self, plan_id):
        self.products.apply_membership(str(self.user_id), plan=None if plan_id == "free" else plan_id)

    def write(self, language, n=1):
        """Learner data in `language`: completed grammar lessons (a progress row per lesson)."""
        with Session(self.engine) as session, session.begin():
            for _ in range(n):
                session.add(GrammarProgress(id=uuid.uuid4(), user_id=self.user_id, language_code=language,
                                            lesson_id=f"lesson-{uuid.uuid4()}", completed_at=NOW))

    def rows(self, table="grammar_progress"):
        with self.engine.connect() as connection:
            return connection.execute(text(f"SELECT count(*) FROM {table} WHERE user_id = :u"),
                                      {"u": self.user_id}).scalar_one()

    def learning_language(self):
        return self.auth.get_account_settings(self.key)["learning_language"]


@pytest.fixture()
def world(pg_engine, monkeypatch):
    key = f"lang-limit-{uuid.uuid4()}"
    previous = quota.runtime()
    previous_repository, previous_user_key = account_settings._repository, account_settings._user_key  # noqa: SLF001
    previous_ownership = language_limit._ownership  # noqa: SLF001
    configure_plan_store(None)
    monkeypatch.delenv(quota.FLAG, raising=False)
    monkeypatch.delenv(quota.METERS_FLAG, raising=False)
    PostgresAuthRepository(pg_engine).upsert_user({"sub": key, "email": f"{key}@example.test", "name": key}, set())
    yield World(pg_engine, key)
    configure_plan_store(None)
    language_limit.configure(previous_ownership)
    account_settings.configure_account_settings(previous_repository, user_key=previous_user_key)
    quota.configure_quota(**{f: getattr(previous, f) for f in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def add_language(monkeypatch, code):
    stub = LanguageProfile.__new__(LanguageProfile)
    for name, value in {"code": code, "enabled": True}.items():
        object.__setattr__(stub, name, value)
    monkeypatch.setitem(language_registry._REGISTRY, code, stub)  # noqa: SLF001


def refused(response, status, category):
    assert response.status_code == status, response.text
    detail = response.json()["detail"]
    assert detail["category"] == category, detail
    return detail


# ------------------------------------------------------------------------------------- the ownership --

def test_the_ownership_read_covers_every_language_scoped_table_and_names_them():
    """Drift guard: a new table with `user_id` -> users and `language_code` is counted automatically; this list makes
    the addition a conscious, reviewed change (and a reminder for `deletion_enumeration.py`)."""
    assert {table.name for table in language_scoped_tables()} == {
        "essay_revisions", "essays", "grammar_progress", "library_collections", "library_items", "listening_progress",
        "reading_ability_projections", "reading_attempts", "reading_legacy_sessions", "saved_words",
        "shadowing_progress", "speaking_attempts", "text_discussions", "user_language_profiles", "vocabulary_decks"}


def test_an_account_holds_its_stored_language_and_every_language_it_has_rows_in(world):
    ownership = PostgresLanguageOwnership(world.engine)
    assert ownership.held(world.key) == set(), "a new account holds nothing"
    world.write("en")
    assert ownership.held(world.key) == {"en"}
    world.auth.update_account_settings(world.key, {"learning_language": "zh"}, world.token(world.client()))
    assert ownership.held(world.key) == {"en", "zh"}, "the stored language counts before it has a row"
    with Session(world.engine) as session, session.begin():
        session.add(UserLanguageProfile(id=uuid.uuid4(), user_id=world.user_id, language_code="vi", created_at=NOW,
                                        updated_at=NOW))
    assert ownership.held(world.key) == {"en", "zh", "vi"}, "a profile row is a language the learner set up"
    other = f"other-{uuid.uuid4()}"
    PostgresAuthRepository(world.engine).upsert_user({"sub": other, "email": f"{other}@e.test", "name": other}, set())
    assert ownership.held(other) == set(), "accounts do not leak into each other"


# ------------------------------------------------------------------------------------- the rule, 1 to 7 --

def test_1_free_with_english_continues_english(world):
    world.write("en")
    client = world.client()
    assert world.post(client, "en").status_code == 200
    assert world.learning_language() == "en"
    assert client.get("/_active").json()["active"] == "en"


def test_2_free_with_english_cannot_add_chinese_and_nothing_changes(world):
    world.write("en", 3)
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    client = world.client()
    token = world.token(client)
    detail = refused(world.post(client, "zh"), 403, "language_limit_reached")
    assert detail["context"] == {"feature": "languages.target", "limit": 1, "owned": 1, "languages": ["en"],
                                 "plan": "free", "upgrade": "#/plan/pricing"}
    assert world.learning_language() == "en" and world.token(client) == token, "stored language and version untouched"
    assert world.rows() == 3 and world.rows("user_language_profiles") == 0, "no row was created or removed"
    assert client.get("/_active").json()["active"] is None, "the session was not moved"


def test_3_plus_holds_english_and_chinese_and_not_a_third(world, monkeypatch):
    add_language(monkeypatch, "xx")
    world.plan("plus")
    world.write("en")
    client = world.client()
    assert world.post(client, "zh").json()["stored"] is True
    world.write("zh")
    assert language_limit.held_by(world.key) == {"en", "zh"}
    refused(world.post(client, "xx"), 403, "language_limit_reached")
    assert world.post(client, "en").status_code == 200 and world.post(client, "zh").status_code == 200


def test_4_downgrade_keeps_both_datasets_both_switchable_and_a_third_is_refused(world, monkeypatch):
    add_language(monkeypatch, "xx")
    world.plan("plus")
    world.write("en", 2)
    client = world.client()
    assert world.post(client, "zh").status_code == 200
    world.write("zh", 4)
    before = world.rows()
    world.plan("free")                                   # the administrator downgrades the account
    for language in ("en", "zh", "en", "zh"):
        done = world.post(client, language)
        assert done.status_code == 200 and done.json()["active"] == language
        assert world.learning_language() == language
    detail = refused(world.post(client, "xx"), 403, "language_limit_reached")
    assert (detail["context"]["limit"], detail["context"]["owned"], detail["context"]["plan"]) == (1, 2, "free")
    assert world.rows() == before == 6, "nothing was deleted"
    # The same through the account settings patch.
    patched = client.patch("/api/account-settings", json={"expected_settings_version": world.token(client),
                                                           "learning_language": "xx"})
    refused(patched, 403, "language_limit_reached")
    assert client.patch("/api/account-settings", json={"expected_settings_version": world.token(client),
                                                        "learning_language": "en"}).status_code == 200


def test_5_no_direct_call_can_bypass(world, monkeypatch):
    add_language(monkeypatch, "xx")
    world.write("en")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    client = world.client()
    # (a) the account settings patch
    refused(client.patch("/api/account-settings", json={"expected_settings_version": world.token(client),
                                                         "learning_language": "zh"}), 403, "language_limit_reached")
    # (b) a switch with no token, which would otherwise change only the session
    refused(world.post(client, "zh", token=False), 403, "language_limit_reached")
    assert client.get("/_active").json()["active"] is None
    # (c) a language the account holds still switches without a token: the session only, as before
    done = world.post(client, "en", token=False)
    assert done.status_code == 200 and done.json()["stored"] is False
    # (d) a stale token is the conflict, not a way round the limit, and writes nothing
    stale = world.token(client)
    client.patch("/api/account-settings", json={"expected_settings_version": stale, "weekly_goal_days": 2})
    assert client.post("/api/platform/language", json={"language": "zh", "settings_version": stale}).status_code == 409
    assert world.learning_language() == "en"
    # (e) an account that never chose, with English in use, cannot make its first choice a second language
    fresh = f"fresh-{uuid.uuid4()}"
    world.auth.upsert_user({"sub": fresh, "email": f"{fresh}@e.test", "name": fresh}, set())
    world.key, world.user_id = fresh, stable_uuid("user", fresh)
    world.write("en")
    refused(world.post(client, "zh", token=False), 403, "language_limit_reached")
    refused(world.post(client, "xx"), 403, "language_limit_reached")
    assert world.learning_language() == ""
    assert world.post(client, "en", token=False).json()["stored"] is True, "its first choice may be a language it uses"


def test_6_an_unreadable_catalogue_or_plan_fails_closed_for_adding_only(world):
    class Down:
        def get_setting(self, key):
            raise RuntimeError("store down")

    world.write("en")
    world.write("zh")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    client = world.client()
    configure_plan_store(Down())
    assert world.post(client, "zh").status_code == 200, "a language it holds needs no catalogue"
    with world.engine.begin() as connection:             # zh is no longer held: no rows, not the stored language
        connection.execute(text("DELETE FROM grammar_progress WHERE user_id = :u AND language_code = 'zh'"),
                           {"u": world.user_id})
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, world.token(client))
    detail = refused(world.post(client, "zh"), 503, "quota_unavailable")
    assert detail["context"]["reason"] == "catalogue" and detail["retryable"] is True
    assert world.learning_language() == "en"
    configure_plan_store(None)
    runtime = quota.runtime()
    quota.configure_quota(repository=runtime.repository, incarnations=runtime.incarnations, settings=None, env=runtime.env,
                          plan_for=lambda key, strict=False: (_ for _ in ()).throw(RuntimeError("subscriptions down")))
    detail = refused(world.post(client, "zh"), 503, "quota_unavailable")
    assert detail["context"]["reason"] == "subscription"


def test_7_an_admin_plan_change_is_the_next_mutations_limit(world):
    world.write("en")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    client = world.client()
    refused(world.post(client, "zh"), 403, "language_limit_reached")
    world.plan("plus")                                   # the administrator sets the plan by hand
    assert world.post(client, "zh").status_code == 200
    world.plan("free")
    world.write("zh")
    assert world.post(client, "en").status_code == 200, "both held: still switchable after the downgrade"


def test_the_limit_comes_from_the_stored_catalogue_not_from_the_code(world, monkeypatch):
    add_language(monkeypatch, "xx")

    class Store:
        value = None

        def get_setting(self, key):
            return {"value": self.value, "updated_at": "t1", "updated_by": "a"} if self.value else None

        def set_setting(self, key, value, *, updated_by="", expected_updated_at=..., audit=None):
            self.value = value
            return {"value": value}

    configure_plan_store(Store())
    world.write("en")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    client = world.client()
    refused(world.post(client, "zh"), 403, "language_limit_reached")
    document = {"version": 2, "plans": [{"id": plan.id, "prices": plan.prices, "entitlements": [
        {"key": "languages.target", "enabled": True, "limit": 2 if plan.id == "free" else 3, "params": {}}]}
        for plan in catalog.PLANS.values()]}
    catalog.save_catalog(document, updated_by="admin")
    assert world.post(client, "zh").status_code == 200, "Free now allows two"
    world.write("zh")
    refused(world.post(client, "xx"), 403, "language_limit_reached")


# --------------------------------------------------------------------------------- switch, account, lock --

def test_off_is_exactly_as_before(world):
    for env in ({quota.FLAG: "off"}, {quota.FLAG: "on", quota.METERS_FLAG: "writing.review"}, {}):
        engine_world = World(world.engine, world.key, env=env)
        engine_world.write("en")
        client = engine_world.client()
        assert engine_world.post(client, "zh").status_code == 200, env
        assert engine_world.post(client, "en", token=False).json()["stored"] is False, "token-less stays session-only"


def test_a_recreated_account_starts_empty(world):
    world.plan("plus")
    world.write("en")
    inc = world.incarnations.ensure_active(str(world.user_id))
    with world.engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO works (id, incarnation_id, language_code, kind, version, lifecycle, payload, updated_sequence,"
            " created_at, updated_at) VALUES (:id, :inc, 'zh', 'draft', 1, 'active', CAST('{}' AS json), 1, :t, :t)"),
            {"id": uuid.uuid4(), "inc": inc, "t": NOW})
    assert language_limit.held_by(world.key) == {"en", "zh"}, "a draft is a language in use"
    # The deletion workflow (deletion_enumeration.py): learner rows deleted, the users columns reset, the incarnation
    # kept as the barrier; re-registration starts the next one.
    world.incarnations.mark_deleted(inc)
    with world.engine.begin() as connection:
        connection.execute(text("DELETE FROM grammar_progress WHERE user_id = :u"), {"u": world.user_id})
        connection.execute(text("UPDATE users SET learning_language = '', settings_updated_at = NULL WHERE id = :u"),
                           {"u": world.user_id})
    assert language_limit.held_by(world.key) == set(), "the old incarnation's works do not follow the account"
    world.incarnations.register_new(str(world.user_id))
    world.plan("free")
    client = world.client()
    assert world.post(client, "zh").status_code == 200, "a recreated Free account adopts a language like a new one"
    refused(world.post(client, "en"), 403, "language_limit_reached")


def test_the_local_account_is_judged_like_any_other(world, monkeypatch):
    monkeypatch.setattr(account_settings, "_auth_enabled", lambda: False)
    with world.engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE user_key = 'legacy'"))
    world.key, world.user_id = "legacy", stable_uuid("user", "legacy")
    client = world.client()
    first = client.post("/api/platform/language", json={"language": "zh"})
    assert first.status_code == 200 and first.json()["stored"] is True, "the local account's row is created by the write"
    refused(world.post(client, "en"), 403, "language_limit_reached")
    assert world.learning_language() == "zh"
    with world.engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE user_key = 'legacy'"))


def test_without_the_ownership_store_every_selection_fails_closed(world):
    world.write("en")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    language_limit.configure(None)
    client = world.client()
    for language in ("en", "zh"):
        refused(world.post(client, language), 503, "quota_unavailable")
    assert world.learning_language() == "en"


@pytest.mark.parametrize("with_token", [True, False])
def test_two_concurrent_additions_at_the_limit_admit_exactly_one(world, monkeypatch, with_token):
    add_language(monkeypatch, "xx")
    world.plan("plus")
    world.write("en")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    world.auth.update_account_settings(world.key, {"weekly_goal_days": 3}, world.token(world.client()))
    real = language_limit.Adoption.guard
    inside = []

    def slow(self, owned):
        inside.append(self.target)
        time.sleep(0.4)       # long enough for the other request to be waiting on the account row
        return real(self, owned)

    monkeypatch.setattr(language_limit.Adoption, "guard", slow)
    barrier = threading.Barrier(2)

    def add(language):
        client = world.client()
        token = world.token(client) if with_token else None
        barrier.wait()
        body = {"language": language, **({"settings_version": token} if token else {})}
        return client.post("/api/platform/language", json=body).status_code

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(add, ["zh", "xx"]))
    assert codes in ([200, 403], [200, 409]), codes
    if not with_token:
        assert codes == [200, 403]
    assert world.learning_language() in {"zh", "xx"}
    assert len(language_limit.held_by(world.key)) == 2, "two languages held, never three"


def test_concurrent_additions_at_the_repository_serialise_on_the_account_row(world, monkeypatch):
    add_language(monkeypatch, "xx")
    world.plan("plus")
    world.write("en")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    in_guard = threading.Event()
    release = threading.Event()
    order = []

    def blocking(owned):
        order.append(("first", sorted(owned)))
        in_guard.set()
        release.wait(5)

    def second(owned):
        order.append(("second", sorted(owned)))
        language_limit.Adoption("xx", world.key).guard(owned)

    def first_write():
        world.auth.update_account_settings(world.key, {"learning_language": "zh"}, None, guard=blocking)

    def second_write():
        in_guard.wait(5)
        try:
            world.auth.update_account_settings(world.key, {"learning_language": "xx"}, None, guard=second)
            return "written"
        except Exception as error:
            return getattr(error, "detail", {}).get("category", repr(error))

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        one = pool.submit(first_write)
        two = pool.submit(second_write)
        time.sleep(0.5)
        assert ("second", ["en"]) not in order, "the second writer waits on the locked account row"
        release.set()
        one.result(10)
        assert two.result(10) == "language_limit_reached"
    assert order[1] == ("second", ["en", "zh"]), "and then reads what the first committed"


# ---------------------------------------------------------------------------------------- Plan & usage --

def test_plan_and_usage_reads_the_held_count_against_the_cap(world):
    world.write("en")
    world.write("zh")
    state = world.service.account_state(world.key)["features"]["languages.target"]
    assert (state["usage_state"], state["used"], state["limit"], state["remaining"]) == ("known", 2, 1, 0)
    assert state["window"] is None and state["resets_at"] is None and state["entitlement_state"] == "enabled"
    world.plan("plus")
    state = world.service.account_state(world.key)["features"]["languages.target"]
    assert (state["used"], state["limit"], state["remaining"]) == (2, 2, 0)
    assert quota.switch()["wired_entitlements"] == ["languages.target"]
    off = World(world.engine, world.key, env={quota.FLAG: "off"})
    assert off.service.account_state(world.key)["features"]["languages.target"]["usage_state"] == "not_metered"


def test_the_ownership_query_runs_on_every_table(world):
    with Session(world.engine) as session:
        assert owned_languages(session, world.user_id) == set()


# ------------------------------------------------------------------------- review of #125 (F1, F2, F5) --

def test_f1_two_token_less_first_choices_of_a_fresh_account_admit_exactly_one(world, monkeypatch):
    """The reviewer's probe: Free, a fresh account, two token-less first choices in parallel. The loser used to skip the
    guard (its token no longer matched), have the 409 swallowed and still move its session."""
    real = language_limit.Adoption.guard

    def slow(self, owned):
        time.sleep(0.6)
        return real(self, owned)

    monkeypatch.setattr(language_limit.Adoption, "guard", slow)
    barrier = threading.Barrier(2)
    clients = {"zh": world.client(), "en": world.client()}

    def pick(language):
        barrier.wait()
        if language == "en":
            time.sleep(0.15)          # read the fresh row after zh started, before zh commits
        return language, clients[language].post("/api/platform/language", json={"language": language})

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = dict(pool.map(pick, ["zh", "en"]))
    assert sorted(r.status_code for r in results.values()) == [200, 403], {k: r.status_code for k, r in results.items()}
    winner = next(language for language, response in results.items() if response.status_code == 200)
    loser = "en" if winner == "zh" else "zh"
    assert refused(results[loser], 403, "language_limit_reached")["context"]["limit"] == 1
    assert world.learning_language() == winner
    assert clients[loser].get("/_active").json()["active"] is None, "the refused session was not moved"
    assert clients[winner].get("/_active").json()["active"] == winner
    world.write(winner)
    assert language_limit.held_by(world.key) == {winner}, "a Free account holds one language"


def _middleware_app(world):
    import auth_support
    from writing_coach.core.request_context import current_language_code

    app = FastAPI()
    app.add_middleware(auth_support.UserIsolationMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(platform_api.router)

    @app.post("/api/learner-write")
    def write():
        language = current_language_code()
        with Session(world.engine) as session, session.begin():
            session.add(GrammarProgress(id=uuid.uuid4(), user_id=world.user_id, language_code=language,
                                        lesson_id=f"lesson-{uuid.uuid4()}", completed_at=NOW))
        return {"language": language}

    return app


def test_f2_a_session_that_never_chose_does_not_write_in_the_default_language(world, monkeypatch):
    """Through the real middleware on PostgreSQL: session A looked before any choice; session B stores zh; A's next
    write must run in zh (never create English rows on a Free account)."""
    import auth_support

    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)
    monkeypatch.setattr(account_settings, "_auth_enabled", lambda: False)
    with world.engine.begin() as connection:
        connection.execute(text("DELETE FROM users WHERE user_key = 'legacy'"))
    world.key, world.user_id = "legacy", stable_uuid("user", "legacy")
    world.auth.upsert_user({"sub": "legacy", "email": "local@localhost.invalid", "name": "Local"}, set())
    try:
        a = TestClient(_middleware_app(world))
        a.get("/api/platform/languages")                       # A looks: nothing stored, so the default
        assert world.post(world.client(), "zh", token=False).json()["stored"] is True
        written = a.post("/api/learner-write")
        assert written.json()["language"] == "zh"
        assert language_limit.held_by("legacy") == {"zh"}, "no English row was created"
        with world.engine.connect() as connection:
            languages = set(connection.execute(text("SELECT DISTINCT language_code FROM grammar_progress WHERE user_id = :u"),
                                               {"u": world.user_id}).scalars())
        assert languages == {"zh"}
    finally:
        with world.engine.begin() as connection:
            connection.execute(text("DELETE FROM users WHERE user_key = 'legacy'"))


def test_feature_not_in_plan_when_the_catalogue_disables_the_entitlement(world):
    class Store:
        def get_setting(self, key):
            document = {"version": 2, "plans": [{"id": plan.id, "prices": plan.prices, "entitlements": [
                {"key": "languages.target", "enabled": plan.id != "free", "limit": 2, "params": {}}]}
                for plan in catalog.PLANS.values()]}
            return {"value": catalog.validate_catalog(document), "updated_at": "t1", "updated_by": "a"}

    world.write("en")
    world.auth.update_account_settings(world.key, {"learning_language": "en"}, "")
    configure_plan_store(Store())
    client = world.client()
    detail = refused(world.post(client, "zh"), 403, "feature_not_in_plan")
    assert detail["context"] == {"feature": "languages.target", "plan": "free", "upgrade": "#/plan/pricing"}
    assert world.learning_language() == "en"
    assert world.post(client, "en").status_code == 200, "a language it holds still switches"
    world.plan("plus")
    assert world.post(client, "zh").status_code == 200, "Plus has the entitlement in this catalogue"
