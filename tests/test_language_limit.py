"""D-170 `languages.target`, hermetic (CI, no PostgreSQL): the count entitlement at the two routes that give an
account a learning language, with an in-memory account store that does what the PostgreSQL one does - lock the account,
hand the guard the languages it holds, write or write nothing.

The real repositories, the real ownership query and the real locks are proved in
`tests/test_language_limit_postgres.py` (run locally with `ORENA_TEST_POSTGRES_URL`).
"""
from __future__ import annotations

import concurrent.futures
import threading
import time
from collections import defaultdict

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.middleware.sessions import SessionMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402

from writing_coach import account_settings  # noqa: E402
from writing_coach.core import language_registry, platform_api  # noqa: E402
from writing_coach.languages.base import LanguageProfile  # noqa: E402
from writing_coach.persistence.auth_repository import AccountRowMissing, SettingsVersionConflict  # noqa: E402
from writing_coach.product import catalog, language_limit, quota  # noqa: E402
from writing_coach.product.catalog import CatalogUnavailable, configure_plan_store  # noqa: E402

pytestmark = pytest.mark.filterwarnings("ignore")


class FakeAccounts:
    """`PostgresAuthRepository.update_account_settings` and `PostgresLanguageOwnership.held`, in memory."""

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.data: dict[str, set[str]] = defaultdict(set)
        self.locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.in_lock = False

    def add(self, key, *, learning="", data=()):
        self.rows[key] = {"learning_language": learning, "interface_language": "", "weekly_goal_days": None,
                          "settings_version": ""}
        self.data[key] = set(data)

    # -- AuthRepository
    def get_account_settings(self, user_key):
        row = self.rows.get(user_key)
        return dict(row) if row else None

    def update_account_settings(self, user_key, changes, expected_token, *, guard=None):
        if user_key not in self.rows:
            raise AccountRowMissing(user_key)
        with self.locks[user_key]:
            row = self.rows[user_key]
            if expected_token is not None and expected_token != row["settings_version"]:
                raise SettingsVersionConflict(row["settings_version"])
            if guard is not None:
                self.in_lock = True
                try:
                    guard(self.held(user_key))
                finally:
                    self.in_lock = False
            row.update(changes)
            row["settings_version"] = str(int(row["settings_version"] or 0) + 1)
            return dict(row)

    def upsert_user(self, info, admin_emails):
        self.add(info["sub"])

    # -- ownership
    def held(self, user_key):
        row = self.rows.get(user_key, {})
        return set(self.data[user_key]) | ({row["learning_language"]} if row.get("learning_language") else set())


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    previous = quota.runtime()
    previous_repository, previous_user_key = account_settings._repository, account_settings._user_key  # noqa: SLF001
    previous_ownership = language_limit._ownership  # noqa: SLF001
    configure_plan_store(None)
    monkeypatch.delenv(quota.FLAG, raising=False)
    monkeypatch.delenv(quota.METERS_FLAG, raising=False)
    yield
    configure_plan_store(None)
    language_limit.configure(previous_ownership)
    account_settings.configure_account_settings(previous_repository, user_key=previous_user_key)
    quota.configure_quota(**{field: getattr(previous, field) for field in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def add_language(monkeypatch, code):
    stub = LanguageProfile.__new__(LanguageProfile)
    for name, value in {"code": code, "enabled": True}.items():
        object.__setattr__(stub, name, value)
    monkeypatch.setitem(language_registry._REGISTRY, code, stub)  # noqa: SLF001


class World:
    def __init__(self, *, plan="free", user="learner", env=None, accounts=None, ownership=True):
        self.accounts = accounts or FakeAccounts()
        self.user = user
        self.plan = {user: plan}
        quota.configure_quota(
            repository=object(), incarnations=object(),
            plan_for=lambda key, strict=False: catalog.plan_by_id(self.plan.get(key, "free"), strict=strict),
            settings=None,
            env={quota.FLAG: "on", quota.METERS_FLAG: "languages.target"} if env is None else env,
        )
        language_limit.configure(self.accounts if ownership else None)
        account_settings.configure_account_settings(self.accounts, user_key=lambda: self.user)
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

    def token(self, client=None):
        return (client or self.client()).get("/api/account-settings").json()["settings_version"]


def refused(response, category):
    assert response.status_code in (403, 503), response.text
    assert response.json()["detail"]["category"] == category, response.text
    return response.json()["detail"]


# ------------------------------------------------------------------------------------------- the rule --

def test_a_free_account_with_english_continues_english_and_cannot_add_chinese():
    world = World()
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    token = world.token(client)
    assert client.post("/api/platform/language", json={"language": "en", "settings_version": token}).status_code == 200
    token = world.token(client)
    response = client.post("/api/platform/language", json={"language": "zh", "settings_version": token})
    detail = refused(response, "language_limit_reached")
    assert response.status_code == 403
    assert detail["context"] == {"feature": "languages.target", "limit": 1, "owned": 1, "languages": ["en"],
                                 "plan": "free", "upgrade": "#/plan/pricing"}
    assert detail["retryable"] is False
    assert world.accounts.rows["learner"]["learning_language"] == "en", "a refusal stores nothing"
    assert world.accounts.rows["learner"]["settings_version"] == token, "and does not move the settings version"
    assert client.get("/_active").json()["active"] != "zh", "and leaves the session on the language it had"


def test_a_plus_account_may_hold_two_and_not_three(monkeypatch):
    add_language(monkeypatch, "xx")
    world = World(plan="plus")
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    assert client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}).json()["stored"]
    assert world.accounts.rows["learner"]["learning_language"] == "zh"
    refused(client.post("/api/platform/language", json={"language": "xx", "settings_version": world.token(client)}),
            "language_limit_reached")
    assert client.post("/api/platform/language", json={"language": "en", "settings_version": world.token(client)}).status_code == 200


def test_after_a_downgrade_both_languages_stay_switchable_and_a_third_is_refused(monkeypatch):
    add_language(monkeypatch, "xx")
    world = World(plan="free")                       # was Plus; the data is kept
    world.accounts.add("learner", learning="zh", data={"en", "zh"})
    client = world.client()
    for language in ("en", "zh", "en"):
        done = client.post("/api/platform/language", json={"language": language, "settings_version": world.token(client)})
        assert done.status_code == 200 and done.json()["active"] == language
    detail = refused(client.post("/api/platform/language", json={"language": "xx", "settings_version": world.token(client)}),
                     "language_limit_reached")
    assert (detail["context"]["limit"], detail["context"]["owned"]) == (1, 2)
    assert world.accounts.data["learner"] == {"en", "zh"}, "nothing is ever deleted"


def test_a_new_account_takes_its_first_language_and_may_change_its_mind_only_to_a_language_it_holds():
    world = World()
    world.accounts.add("learner")
    client = world.client()
    assert client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}).status_code == 200
    refused(client.post("/api/platform/language", json={"language": "en", "settings_version": world.token(client)}),
            "language_limit_reached")


def test_unlimited_and_disabled_entitlements(monkeypatch):
    add_language(monkeypatch, "xx")
    document = {"version": 2, "plans": [
        {"id": plan.id, "prices": plan.prices, "entitlements": [
            {"key": "languages.target", "enabled": plan.id != "pro", "limit": 5 if plan.id == "plus" else 1, "params": {}}]}
        for plan in catalog.PLANS.values()]}

    class Store:
        def get_setting(self, key):
            return {"value": catalog.validate_catalog(document), "updated_at": "t", "updated_by": "a"}

    configure_plan_store(Store())
    world = World(plan="plus")
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    assert client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}).status_code == 200
    world.plan["learner"] = "pro"                     # languages.target disabled for Pro
    detail = refused(client.post("/api/platform/language", json={"language": "xx", "settings_version": world.token(client)}),
                     "feature_not_in_plan")
    assert detail["context"]["feature"] == "languages.target"
    assert client.post("/api/platform/language", json={"language": "en", "settings_version": world.token(client)}).status_code == 200


# --------------------------------------------------------------------------- every path, no way round --

def test_the_account_settings_patch_cannot_add_a_language_either():
    world = World()
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    response = client.patch("/api/account-settings", json={"expected_settings_version": world.token(client),
                                                           "learning_language": "zh"})
    refused(response, "language_limit_reached")
    assert world.accounts.rows["learner"]["learning_language"] == "en"
    ok = client.patch("/api/account-settings", json={"expected_settings_version": world.token(client), "weekly_goal_days": 3})
    assert ok.status_code == 200, "a write that does not touch the learning language is not judged"


def test_a_switch_without_a_token_cannot_slip_a_new_language_in_through_the_session_only():
    world = World()
    world.accounts.add("learner", learning="en", data={"en"})
    world.accounts.rows["learner"]["settings_version"] = "1"
    client = world.client()
    refused(client.post("/api/platform/language", json={"language": "zh"}), "language_limit_reached")
    assert client.get("/_active").json()["active"] is None
    again = client.post("/api/platform/language", json={"language": "en"})
    assert again.status_code == 200 and again.json()["stored"] is False, "a language it holds still switches the session only"


def test_a_first_choice_without_a_token_is_judged_too():
    world = World()
    world.accounts.add("learner", data={"en"})            # never chose, but has written English
    client = world.client()
    refused(client.post("/api/platform/language", json={"language": "zh"}), "language_limit_reached")
    assert world.accounts.rows["learner"]["learning_language"] == ""
    assert client.post("/api/platform/language", json={"language": "en"}).json()["stored"] is True


def test_a_stale_token_is_a_conflict_not_a_limit_and_writes_nothing():
    world = World()
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    stale = world.token(client)
    assert client.patch("/api/account-settings", json={"expected_settings_version": stale, "weekly_goal_days": 2}).status_code == 200
    response = client.post("/api/platform/language", json={"language": "zh", "settings_version": stale})
    assert response.status_code == 409
    assert world.accounts.rows["learner"]["learning_language"] == "en"


def test_the_local_account_is_judged_like_any_other():
    """Authentication off: the one local account ("legacy") has its row created on its first settings write, and the
    first selection is that write - judged and recorded like anyone's."""
    world = World(user="legacy")
    client = world.client()
    first = client.post("/api/platform/language", json={"language": "zh"})
    assert first.status_code == 200 and first.json()["stored"] is True
    assert world.accounts.rows["legacy"]["learning_language"] == "zh"
    refused(client.post("/api/platform/language", json={"language": "en", "settings_version": world.token(client)}),
            "language_limit_reached")
    assert world.accounts.rows["legacy"]["learning_language"] == "zh"


def test_an_authenticated_account_without_a_row_cannot_adopt_a_language_it_cannot_record(monkeypatch):
    monkeypatch.setattr(account_settings, "_auth_enabled", lambda: True)
    world = World(user="stranger")
    client = world.client()
    response = client.post("/api/platform/language", json={"language": "zh"})
    assert response.status_code == 503 and response.json()["detail"]["reason"] == "account_settings_unavailable"
    assert client.get("/_active").json()["active"] is None


# ------------------------------------------------------------------------------- switch and failure modes --

def test_off_or_unlisted_is_exactly_as_before(monkeypatch):
    for env in ({quota.FLAG: "off"}, {quota.FLAG: "on", quota.METERS_FLAG: "writing.review"}, {}):
        world = World(env=env)
        world.accounts.add("learner", learning="en", data={"en"})
        client = world.client()
        first = client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)})
        assert first.status_code == 200 and first.json()["stored"] is True, env
        second = client.post("/api/platform/language", json={"language": "en"})
        assert second.json()["stored"] is False, "token-less switching behaves as it did"


def test_enforced_without_an_ownership_store_fails_closed_for_every_selection():
    world = World(ownership=False)
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    for language in ("en", "zh"):
        detail = refused(client.post("/api/platform/language", json={"language": language,
                                                                     "settings_version": world.token(client)}),
                         "quota_unavailable")
        assert detail["retryable"] is True
    assert world.accounts.rows["learner"]["learning_language"] == "en"


def test_the_unreadable_catalogue_fails_closed_for_adding_only():
    class Down:
        def get_setting(self, key):
            raise RuntimeError("store down")

    world = World()
    world.accounts.add("learner", learning="en", data={"en", "zh"})
    configure_plan_store(Down())
    client = world.client()
    with pytest.raises(CatalogUnavailable):
        catalog.current_plans(strict=True)
    ok = client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)})
    assert ok.status_code == 200, "a language it holds needs no catalogue"
    world.accounts.data["learner"].discard("zh")
    world.accounts.rows["learner"]["learning_language"] = "en"
    detail = refused(client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}),
                     "quota_unavailable")
    assert detail["context"]["reason"] == "catalogue"
    assert world.accounts.rows["learner"]["learning_language"] == "en"


def test_an_unreadable_plan_fails_closed_for_adding():
    world = World()
    world.accounts.add("learner", learning="en", data={"en"})
    quota.configure_quota(repository=object(), incarnations=object(),
                          plan_for=lambda key, strict=False: (_ for _ in ()).throw(RuntimeError("subscriptions down")),
                          settings=None, env={quota.FLAG: "on", quota.METERS_FLAG: "languages.target"})
    client = world.client()
    detail = refused(client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}),
                     "quota_unavailable")
    assert detail["context"]["reason"] == "subscription"


def test_an_admin_plan_change_applies_to_the_next_mutation():
    world = World(plan="free")
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    refused(client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}),
            "language_limit_reached")
    world.plan["learner"] = "plus"                    # the administrator sets the plan by hand
    assert client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}).status_code == 200


def test_an_admin_catalogue_change_applies_at_once_in_the_process_that_saved_it(monkeypatch):
    add_language(monkeypatch, "xx")

    class Store:
        def __init__(self):
            self.value = None

        def get_setting(self, key):
            return {"value": self.value, "updated_at": "t1", "updated_by": "a"} if self.value else None

        def set_setting(self, key, value, *, updated_by="", expected_updated_at=..., audit=None):
            self.value = value
            return {"value": value}

    store = Store()
    configure_plan_store(store)
    world = World(plan="free")
    world.accounts.add("learner", learning="en", data={"en"})
    client = world.client()
    refused(client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}),
            "language_limit_reached")
    document = catalog.validate_catalog({"version": 2, "plans": [
        {"id": plan.id, "prices": plan.prices, "entitlements": [
            {"key": "languages.target", "enabled": True, "limit": 2 if plan.id == "free" else 3, "params": {}}]}
        for plan in catalog.PLANS.values()]})
    catalog.save_catalog(document, updated_by="admin")
    assert client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}).status_code == 200
    refused(client.post("/api/platform/language", json={"language": "xx", "settings_version": world.token(client)}),
            "language_limit_reached")


def test_two_concurrent_additions_at_the_limit_admit_exactly_one(monkeypatch):
    add_language(monkeypatch, "xx")
    world = World(plan="plus")
    world.accounts.add("learner", learning="en", data={"en"})
    real = language_limit.Adoption.guard

    def slow(self, owned):
        time.sleep(0.2)            # both requests are inside their write at once unless the account is locked
        return real(self, owned)

    monkeypatch.setattr(language_limit.Adoption, "guard", slow)
    barrier = threading.Barrier(2)

    def add(language):
        client = world.client()
        token = world.token(client)
        barrier.wait()
        return client.post("/api/platform/language", json={"language": language}).status_code if False else \
            client.post("/api/platform/language", json={"language": language, "settings_version": token}).status_code

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(add, ["zh", "xx"]))
    # One wins; the other either lost the race on the version token (409) or was refused at the limit (403).
    assert codes in ([200, 403], [200, 409]), codes


def test_concurrent_additions_without_a_token_admit_exactly_one(monkeypatch):
    add_language(monkeypatch, "xx")
    world = World(plan="plus")
    world.accounts.add("learner", learning="en", data={"en"})
    world.accounts.rows["learner"]["settings_version"] = "1"
    real = language_limit.Adoption.guard
    monkeypatch.setattr(language_limit.Adoption, "guard", lambda self, owned: (time.sleep(0.2), real(self, owned))[1])
    barrier = threading.Barrier(2)

    def add(language):
        client = world.client()
        barrier.wait()
        return client.post("/api/platform/language", json={"language": language}).status_code

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(add, ["zh", "xx"]))
    assert codes == [200, 403], codes
    assert world.accounts.rows["learner"]["learning_language"] in {"zh", "xx"}


# ------------------------------------------------------------------------------------- build and display --

def test_languages_target_is_an_enforceable_entitlement_not_a_bucket_meter():
    assert "languages.target" in quota.WIRED_ENTITLEMENTS and "languages.target" not in quota.WIRED_METERS
    assert quota.validate_switch_setting({"enabled": True, "meters": ["languages.target", "writing.review"]}) == {
        "enabled": True, "meters": ["writing.review", "languages.target"]}
    with pytest.raises(ValueError, match="Not enforceable"):
        quota.validate_switch_setting({"enabled": True, "meters": ["nonsense"]})
    with pytest.raises(ValueError, match="count entitlement"):
        with quota.admit("languages.target"):
            pass
    with pytest.raises(ValueError, match="count entitlement"):
        quota.check_available("languages.target")
    state = quota.switch()
    assert state["wired_entitlements"] == ["languages.target"] and state["wired_meters"] == list(quota.WIRED_METERS)


def test_plan_and_usage_reports_what_the_account_holds_against_the_cap(monkeypatch):
    from writing_coach.product.service import ProductService

    world = World(plan="free")
    world.accounts.add("learner", learning="zh", data={"en", "zh"})
    service = ProductService(repository=type("R", (), {"get_subscription": lambda self, key: None})(), usage=quota.usage_for)
    feature = service.account_state("learner")["features"]["languages.target"]
    assert (feature["usage_state"], feature["used"], feature["limit"], feature["remaining"]) == ("known", 2, 1, 0)
    assert feature["window"] is None and feature["resets_at"] is None and feature["entitlement_state"] == "enabled"
    quota.configure_quota(repository=object(), incarnations=object(), plan_for=lambda key, strict=False: catalog.FREE,
                          settings=None, env={quota.FLAG: "off"})
    assert service.account_state("learner")["features"]["languages.target"]["usage_state"] == "not_metered"


# ------------------------------------------------------------------------- review of #125 (F1, F2, F6) --

def test_f1_two_token_less_first_choices_race_and_only_one_is_admitted(monkeypatch):
    """Free, an account that never chose, no token: the loser of the race must be refused and its session left alone."""
    add_language(monkeypatch, "xx")
    world = World(plan="free")
    world.accounts.add("learner")
    real = language_limit.Adoption.guard

    def slow(self, owned):
        time.sleep(0.3)
        return real(self, owned)

    monkeypatch.setattr(language_limit.Adoption, "guard", slow)
    barrier = threading.Barrier(2)
    clients = {"zh": world.client(), "en": world.client()}

    def pick(language):
        barrier.wait()
        if language == "en":
            time.sleep(0.1)
        return language, clients[language].post("/api/platform/language", json={"language": language})

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results = dict(pool.map(pick, ["zh", "en"]))
    codes = sorted(response.status_code for response in results.values())
    assert codes == [200, 403], {language: response.status_code for language, response in results.items()}
    winner = next(language for language, response in results.items() if response.status_code == 200)
    loser = "en" if winner == "zh" else "zh"
    assert world.accounts.rows["learner"]["learning_language"] == winner
    assert clients[loser].get("/_active").json()["active"] is None, "the refused session was not moved"
    assert clients[winner].get("/_active").json()["active"] == winner
    assert world.accounts.held("learner") == {winner}


def test_f6_the_limit_is_read_before_the_account_row_is_locked(monkeypatch):
    """No catalogue or subscription read (pooled connections) happens while the guard holds the account lock."""
    world = World(plan="plus")
    world.accounts.add("learner", learning="en", data={"en"})
    runtime = quota.runtime()
    reads = []

    def plan_for(key, strict=False):
        reads.append(world.accounts.in_lock)
        return catalog.plan_by_id("plus", strict=strict)

    quota.configure_quota(repository=runtime.repository, incarnations=runtime.incarnations, plan_for=plan_for,
                          settings=None, env=runtime.env)
    client = world.client()
    assert client.post("/api/platform/language", json={"language": "zh", "settings_version": world.token(client)}).status_code == 200
    assert reads and not any(reads), reads


def test_f7_a_plan_without_the_entitlement_refuses_even_a_first_language():
    """Recorded for administrators (D-170): disabling `languages.target` for a plan blocks onboarding on it."""
    document = {"version": 2, "plans": [
        {"id": plan.id, "prices": plan.prices, "entitlements": [
            {"key": "languages.target", "enabled": plan.id != "free", "limit": 2, "params": {}}]}
        for plan in catalog.PLANS.values()]}

    class Store:
        def get_setting(self, key):
            return {"value": catalog.validate_catalog(document), "updated_at": "t", "updated_by": "a"}

    configure_plan_store(Store())
    world = World(plan="free")
    world.accounts.add("learner")
    client = world.client()
    refused(client.post("/api/platform/language", json={"language": "en", "settings_version": world.token(client)}),
            "feature_not_in_plan")
    world.accounts.data["learner"].add("en")
    assert client.post("/api/platform/language", json={"language": "en", "settings_version": world.token(client)}).status_code == 200


# --- F2: the middleware path ----------------------------------------------------------------------------------

def _middleware_app(accounts):
    import auth_support
    from writing_coach.core.request_context import current_language_code

    app = FastAPI()
    app.add_middleware(auth_support.UserIsolationMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")
    app.include_router(platform_api.router)

    @app.post("/api/slow-write")
    def slow_write():
        time.sleep(0.2)
        accounts.data["legacy"].add(current_language_code())
        return {"language": current_language_code()}

    @app.post("/api/learner-write")
    def write():
        accounts.data["legacy"].add(current_language_code())       # a learner row, in the request's language
        return {"language": current_language_code()}

    @app.get("/api/learner-read")
    def read():
        return {"language": current_language_code()}

    return app


def _f2_world(monkeypatch, *, enforced):
    import auth_support

    monkeypatch.setattr(auth_support, "AUTH_ENABLED", False)
    world = World(user="legacy", env=None if enforced else {quota.FLAG: "off"})
    world.accounts.add("legacy")
    return world


def test_f2_a_session_that_never_chose_asks_again_while_the_count_is_enforced(monkeypatch):
    world = _f2_world(monkeypatch, enforced=True)
    a = TestClient(_middleware_app(world.accounts))
    assert a.get("/api/learner-read").json()["language"] == "en", "nothing stored yet: the default"
    # Another session stores zh.
    b = world.client()
    assert b.post("/api/platform/language", json={"language": "zh"}).json()["stored"] is True
    assert a.post("/api/learner-write").json()["language"] == "zh", "A re-read the account instead of keeping 'en'"
    assert world.accounts.held("legacy") == {"zh"}, "no English row was created on a Free account"


def test_f2_without_the_count_enforced_the_session_keeps_asking_once(monkeypatch):
    world = _f2_world(monkeypatch, enforced=False)
    a = TestClient(_middleware_app(world.accounts))
    assert a.get("/api/learner-read").json()["language"] == "en"
    world.accounts.rows["legacy"]["learning_language"] = "zh"
    assert a.get("/api/learner-read").json()["language"] == "en", "as before: one lookup per session (proposal I2)"


def test_f2_an_unreadable_account_refuses_a_write_but_not_a_read_while_enforced(monkeypatch):
    world = _f2_world(monkeypatch, enforced=True)
    a = TestClient(_middleware_app(world.accounts))
    original = world.accounts.get_account_settings
    monkeypatch.setattr(world.accounts, "get_account_settings", lambda key: (_ for _ in ()).throw(RuntimeError("down")))
    write = a.post("/api/learner-write")
    assert write.status_code == 503 and write.json()["detail"]["category"] == "quota_unavailable"
    assert write.json()["detail"]["context"]["reason"] == "language" and write.json()["detail"]["retryable"] is True
    assert world.accounts.data["legacy"] == set(), "nothing was written in a language nobody checked"
    assert a.get("/api/learner-read").status_code == 200, "a read still answers"
    monkeypatch.setattr(world.accounts, "get_account_settings", original)
    gated = a.post("/api/learner-write")
    assert gated.status_code == 409 and gated.json()["detail"]["category"] == "learning_language_required"
    assert world.accounts.data["legacy"] == set()


# --- F8: an account that never chose writes no learner rows in the default language ------------------------------

def test_f8_a_never_chosen_account_is_asked_for_its_language_before_any_learner_write(monkeypatch):
    world = _f2_world(monkeypatch, enforced=True)
    a = TestClient(_middleware_app(world.accounts))
    refused_write = a.post("/api/learner-write")
    detail = refused_write.json()["detail"]
    assert refused_write.status_code == 409 and detail["category"] == "learning_language_required"
    assert detail["retryable"] is False and detail["context"] == {"feature": "languages.target"}
    assert world.accounts.data["legacy"] == set(), "nothing was written"
    assert a.get("/api/learner-read").status_code == 200, "reads are not gated"
    # The routes that write no learner row still work, and choosing the language ends the gate.
    chose = world.client()
    assert chose.post("/api/platform/language", json={"language": "zh"}).status_code == 200
    assert a.post("/api/learner-write").json()["language"] == "zh"


def test_f8_an_english_learner_from_before_the_count_is_not_locked_out(monkeypatch):
    """Never stored a choice, but holds English by data: the default language is one the account holds."""
    world = _f2_world(monkeypatch, enforced=True)
    world.accounts.data["legacy"].add("en")
    a = TestClient(_middleware_app(world.accounts))
    assert a.post("/api/learner-write").json()["language"] == "en"


def test_f8_in_flight_write_cannot_land_in_the_default_language_after_another_adoption(monkeypatch):
    """The reviewer's probe: the write is decided at its start, the adoption happens during it."""
    world = _f2_world(monkeypatch, enforced=True)
    a = TestClient(_middleware_app(world.accounts))
    a.get("/api/learner-read")                                  # the session has looked: nothing stored
    written = a.post("/api/slow-write")
    assert written.status_code == 409, "refused at its start, so it can never land in English after an adoption"
    adopted = a.post("/api/platform/language", json={"language": "zh"})
    assert adopted.status_code == 200
    assert world.accounts.held("legacy") == {"zh"}


def test_f8_not_enforced_a_never_chosen_account_writes_as_before(monkeypatch):
    world = _f2_world(monkeypatch, enforced=False)
    a = TestClient(_middleware_app(world.accounts))
    assert a.post("/api/learner-write").json()["language"] == "en"


def test_f8_the_exempt_routes_are_exactly_the_ones_that_write_no_learner_rows():
    """Default-deny: a route is covered unless it is listed here. A new mutating route that is not a learner-row writer must
    be added to `LANGUAGE_FREE_PREFIXES` AND to this list on purpose; a new learner-data writer needs neither."""
    import app as app_module

    paths = app_module.app.openapi()["paths"]
    mutating = {(method.upper(), path) for path, operations in paths.items() for method in operations
                if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}}
    exempt = {route for route in mutating if language_limit.writes_no_learner_rows(route[1])}
    non_admin = {route for route in exempt if "admin" not in route[1].strip("/").split("/")}
    assert non_admin == {
        ("PATCH", "/api/account-settings"), ("POST", "/api/auth/native/exchange"), ("POST", "/api/billing/checkout"),
        ("POST", "/api/billing/webhooks/{gateway}"), ("POST", "/api/feedback"), ("POST", "/api/platform/language"),
    }, sorted(non_admin)
    for route in [("POST", "/api/evaluate"), ("PUT", "/api/learner-profile"), ("PATCH", "/api/learner-profile"),
                  ("POST", "/api/agent/turn"), ("PUT", "/api/drafts/{key}"), ("POST", "/api/library/vocabulary"),
                  ("POST", "/api/listening/progress"), ("PUT", "/api/grammar/v1/progress/{point_id}"),
                  ("POST", "/api/speech/attempts"), ("POST", "/api/texts/discussion/turns")]:
        assert route in mutating and route not in exempt, route
    assert len(mutating - exempt) > 60, "every other mutating route is covered"


def test_f2_a_session_with_its_own_language_is_not_re_read(monkeypatch):
    world = _f2_world(monkeypatch, enforced=True)
    a = TestClient(_middleware_app(world.accounts))
    chosen = world.client()
    assert chosen.post("/api/platform/language", json={"language": "zh"}).status_code == 200
    reads = []
    original = account_settings.stored_learning_language
    monkeypatch.setattr(account_settings, "stored_learning_language", lambda key: reads.append(key) or original(key))
    assert a.get("/api/learner-read").json()["language"] == "zh"      # seeded once
    for _ in range(3):
        a.get("/api/learner-read")
    assert len(reads) == 1, "once the session has a language it costs no more reads"
