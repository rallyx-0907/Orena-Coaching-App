"""D-161 plan quota enforcement, hermetic (CI, SQLite): catalogue v2, the switch, windows, operation ids,
the 429/503 envelope and the two writing routes.

The quota store here is an in-memory TEST DOUBLE of `PostgresQuotaRepository`'s protocol (reserve with
`limit_policy='current'`, dispatch, settle, release, latest_buckets, stale_dispatched) - never a runtime
store. The same behaviour against real PostgreSQL is proved in `tests/test_quota_gate_postgres.py` and
`tests/test_orena_quota_persistence_postgres.py`.
"""
from __future__ import annotations

import copy
import threading
from datetime import UTC, datetime, timedelta


import pytest

pytest.importorskip("fastapi")
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from writing_coach.product import catalog, quota  # noqa: E402
from writing_coach.product.catalog import (  # noqa: E402
    CatalogUnavailable,
    PlanCatalogInvalid,
    configure_plan_store,
    current_catalog,
    current_plans,
    validate_catalog,
)
from writing_coach.reference_backbone import Quota, reserve_decision  # noqa: E402


# ---------------------------------------------------------------- doubles --

class MemorySettings:
    def __init__(self, rows=None, *, fail=False):
        self.rows = rows or {}
        self.fail = fail

    def get_setting(self, key):
        if self.fail:
            raise RuntimeError("store down")
        return copy.deepcopy(self.rows.get(key))

    def set_setting(self, key, value, *, updated_by="", expected_updated_at=..., audit=None):
        self.rows[key] = {"value": copy.deepcopy(value), "updated_at": "2026-10-09T10:00:00+00:00", "updated_by": updated_by}
        return copy.deepcopy(self.rows[key])


class FakeQuotaRepository:
    """In-memory test double of the repository protocol the service uses (current-limit mode only)."""

    def __init__(self):
        self.buckets: dict[tuple, dict] = {}
        self.reservations: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.calls: list[str] = []

    def latest_buckets(self, incarnation_id, meters):
        self.calls.append("latest_buckets")
        out = {}
        for (inc, meter, _w), bucket in self.buckets.items():
            if inc == incarnation_id and meter in meters:
                if meter not in out or bucket["window_end"] > out[meter]["window_end"]:
                    out[meter] = dict(bucket)
        return out

    def reserve(self, *, incarnation_id, meter, window, operation_id, requested_units, entitlement="allowed",
                limit_policy="frozen"):
        assert limit_policy == "current"
        self.calls.append("reserve")
        with self.lock:
            recorded = self.reservations.get(operation_id)
            if recorded is not None:
                same = recorded["key"] == (incarnation_id, meter, window.window_id) and recorded["units"] == requested_units
                return {"status": "duplicate", "state": recorded["state"]} if same else {"status": "payload_conflict"}
            key = (incarnation_id, meter, window.window_id)
            bucket = self.buckets.setdefault(key, {
                "window_id": window.window_id, "window_start": window.window_start, "window_end": window.window_end,
                "unit_limit": window.unit_limit, "consumed": 0, "reserved": 0, "meter": meter,
            })
            verdict = reserve_decision(Quota(window.unit_limit, bucket["consumed"], bucket["reserved"]), requested_units)
            if verdict != "admit":
                return {"status": verdict, "limit": window.unit_limit, "consumed": bucket["consumed"],
                        "reserved": bucket["reserved"]}
            bucket["reserved"] += requested_units
            self.reservations[operation_id] = {"key": key, "units": requested_units, "state": "reserved",
                                               "updated_at": datetime.now(UTC)}
            return {"status": "admit", "admitted_units": requested_units, "state": "reserved"}

    def dispatch(self, *, operation_id, dispatch_ref=None):
        self.calls.append("dispatch")
        with self.lock:
            row = self.reservations[operation_id]
            if row["state"] == "dispatched":
                return {"status": "duplicate"}
            row["state"] = "dispatched"
            return {"status": "dispatch"}

    def settle(self, *, operation_id, actual_units, outcome_ref=None):
        self.calls.append(f"settle:{actual_units}")
        with self.lock:
            row = self.reservations.get(operation_id)
            if row is None or row["state"] in ("settled", "released"):
                return {"status": "duplicate"}
            bucket = self.buckets[row["key"]]
            bucket["reserved"] -= row["units"]
            bucket["consumed"] += actual_units
            row["state"] = "settled"
            return {"status": "settle"}

    def release(self, *, operation_id):
        self.calls.append("release")
        with self.lock:
            row = self.reservations.get(operation_id)
            if row is None or row["state"] != "reserved":
                return {"status": "duplicate"}
            self.buckets[row["key"]]["reserved"] -= row["units"]
            row["state"] = "released"
            return {"status": "release"}

    def stale_dispatched(self, older_than, limit, states=("dispatched",), meters=None):
        return [{"operation_id": op, "state": row["state"], "admitted_units": row["units"]}
                for op, row in self.reservations.items() if row["state"] in states and row["updated_at"] < older_than
                and (meters is None or row["key"][1] in meters)]


class FakeIncarnations:
    def ensure_active(self, account):
        return f"inc-{account}"

    def resolve(self, account):
        return f"inc-{account}"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    """Every test starts with the default catalogue, no stored switch and the runtime the app configured."""
    previous_runtime = quota.runtime()
    configure_plan_store(None)
    monkeypatch.delenv(quota.FLAG, raising=False)
    monkeypatch.delenv(quota.METERS_FLAG, raising=False)
    yield
    configure_plan_store(None)
    quota.configure_quota(**{field: getattr(previous_runtime, field) for field in
                             ("repository", "incarnations", "plan_for", "settings", "reason", "env", "clock")})


def enforced_runtime(*, plan_id="free", repository=None, clock=None, env=None):
    repository = repository or FakeQuotaRepository()
    quota.configure_quota(
        repository=repository, incarnations=FakeIncarnations(),
        plan_for=lambda user_key, strict=False: catalog.plan_by_id(plan_id, strict=strict),
        settings=MemorySettings(), env=env if env is not None else {quota.FLAG: "on", quota.METERS_FLAG: "writing.review"},
        clock=clock or (lambda: datetime(2026, 10, 9, 12, 0, tzinfo=UTC)),
    )
    return repository


# ---------------------------------------------------------- catalogue v2 --

V1_DOC = {"version": 1, "plans": [
    {"id": "free", "prices": {"monthly": {"USD": 0, "VND": 0}, "yearly": {"USD": 0, "VND": 0}},
     "entitlements": [{"key": "writing.evaluate", "enabled": True, "monthly_limit": 30}]},
    {"id": "plus", "prices": {"monthly": {"USD": 7.77, "VND": 177000}, "yearly": {"USD": 70, "VND": 1700000}},
     "entitlements": [{"key": "dictionary.lookup", "enabled": True, "monthly_limit": 800}]},
    {"id": "pro", "prices": {"monthly": {"USD": 17.77, "VND": 377000}, "yearly": {"USD": 170, "VND": 3700000}},
     "entitlements": []},
]}


def test_a_stored_v1_catalogue_keeps_its_prices_and_takes_the_new_meters():
    configure_plan_store(MemorySettings({catalog.PLAN_SETTING_KEY: {"value": V1_DOC, "updated_at": "t1", "updated_by": "a"}}))
    plans, revision = current_catalog(strict=True)
    assert plans["plus"].prices["monthly"] == {"USD": 7.77, "VND": 177000}, "prices are never dropped to defaults"
    assert plans["pro"].prices["yearly"] == {"USD": 170, "VND": 3700000}
    assert plans["plus"].entitlement_map()["writing.review"].limit == 10, "v1 limits are of features that no longer exist"
    assert "dictionary.lookup" not in plans["plus"].entitlement_map()
    assert revision == catalog.catalog_revision("t1") != "default"


def test_saving_a_v1_document_is_refused_rather_than_losing_its_limits():
    with pytest.raises(PlanCatalogInvalid, match="old plan features"):
        validate_catalog(V1_DOC)
    assert validate_catalog(V1_DOC, accept_v1=True)["version"] == 2


def test_the_strict_read_fails_closed_and_the_display_read_does_not():
    configure_plan_store(MemorySettings(fail=True))
    with pytest.raises(CatalogUnavailable):
        current_plans(strict=True)
    assert current_plans()["free"].entitlement_map()["writing.review"].limit == 2, "display shows the built-in values"
    with pytest.raises(CatalogUnavailable):
        current_plans(strict=True), "a failed read is never cached as defaults"


def test_an_unreadable_stored_document_is_unavailable_for_enforcement():
    configure_plan_store(MemorySettings({catalog.PLAN_SETTING_KEY: {"value": {"version": 2, "plans": "x"}, "updated_at": "t"}}))
    with pytest.raises(CatalogUnavailable):
        current_plans(strict=True)


def test_an_absent_document_is_the_defaults_even_strictly():
    configure_plan_store(MemorySettings())
    plans, revision = current_catalog(strict=True)
    assert plans["pro"].entitlement_map()["orena.message"].limit == 1000
    assert revision == "default"
    assert catalog.policy_version("free", revision) == "cdefault:free"


# ------------------------------------------------------------------ switch --

def test_the_switch_is_off_by_default_and_admits_without_touching_a_store():
    repository = FakeQuotaRepository()
    quota.configure_quota(repository=repository, incarnations=FakeIncarnations(),
                          plan_for=lambda *a, **k: catalog.FREE, settings=MemorySettings(), env={})
    assert quota.switch()["state"] == "off"
    with quota.admit("writing.review", request_digest="x") as ticket:
        ticket.dispatch("p")
        ticket.settle(1)
    assert ticket is quota.NULL_TICKET
    assert repository.calls == [], "off writes no bucket"


def test_the_setting_switches_it_on_and_the_environment_wins_when_set():
    settings = MemorySettings({quota.SETTING_KEY: {"value": {"enabled": True, "meters": ["writing.review"]}}})
    quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(),
                          plan_for=lambda *a, **k: catalog.FREE, settings=settings, env={})
    assert quota.switch()["state"] == "enforced" and quota.switch()["source"] == "setting"
    quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(),
                          plan_for=lambda *a, **k: catalog.FREE, settings=settings, env={quota.FLAG: "off"})
    assert quota.switch()["state"] == "off" and quota.switch()["source"] == "environment"


def test_only_wired_meters_can_be_listed():
    assert set(quota.WIRED_METERS) == {"writing.review", "orena.message", "pronunciation.audio", "media.import"}
    assert quota.validate_switch_setting({"enabled": True, "meters": ["pronunciation.audio", "writing.review"]}) == {
        "enabled": True, "meters": ["writing.review", "pronunciation.audio"]}
    with pytest.raises(ValueError, match="languages.target"):
        quota.validate_switch_setting({"enabled": True, "meters": ["languages.target"]})
    quota.configure_quota(settings=MemorySettings(),
                          env={quota.FLAG: "on", quota.METERS_FLAG: "languages.target,writing.review"})
    assert quota.switch()["meters"] == ["writing.review"], "an unwired meter enforces nothing and is not listed"


def test_on_without_a_store_is_unavailable_and_refuses_with_503():
    quota.configure_quota(settings=MemorySettings(), env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"},
                          reason="no_postgresql")
    assert quota.switch()["state"] == "unavailable"
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="x"):
            pytest.fail("the block must not run")
    assert refused.value.status_code == 503
    assert refused.value.detail["category"] == "quota_unavailable"
    assert refused.value.detail["retryable"] is True


# ----------------------------------------------------------------- windows --

NOW = datetime(2026, 10, 9, 18, 30, tzinfo=UTC)  # 2026-10-10 01:30 in Ho Chi Minh City (UTC+7)


def test_a_day_is_the_learners_local_day():
    window = quota.window_for("day", now=NOW, zone_name="Asia/Ho_Chi_Minh", previous=None)
    assert window.window_id == "D:2026-10-10@Asia/Ho_Chi_Minh"
    assert window.start == datetime(2026, 10, 9, 17, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 10, 10, 17, 0, tzinfo=UTC), "resets at local midnight, as a true instant"


def test_a_month_starts_at_local_midnight_on_the_first():
    window = quota.window_for("month", now=datetime(2026, 10, 31, 17, 30, tzinfo=UTC), zone_name="Asia/Ho_Chi_Minh", previous=None)
    assert window.window_id == "M:2026-11@Asia/Ho_Chi_Minh"
    assert window.start == datetime(2026, 10, 31, 17, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 11, 30, 17, 0, tzinfo=UTC)
    december = quota.window_for("month", now=datetime(2026, 12, 15, tzinfo=UTC), zone_name="UTC", previous=None)
    assert december.end == datetime(2027, 1, 1, tzinfo=UTC)


def _bucket(window):
    return {"window_id": window.window_id, "window_start": window.start, "window_end": window.end}


def test_a_timezone_change_never_reopens_or_resets_the_current_window():
    first = quota.window_for("day", now=NOW, zone_name="Asia/Ho_Chi_Minh", previous=None)
    later = quota.window_for("day", now=NOW + timedelta(hours=2), zone_name="America/Los_Angeles", previous=_bucket(first))
    assert later.window_id == first.window_id and later.end == first.end


def test_a_westward_change_at_the_boundary_starts_where_the_last_window_ended_and_is_not_short():
    first = quota.window_for("day", now=NOW, zone_name="Asia/Ho_Chi_Minh", previous=None)
    after = first.end + timedelta(minutes=1)
    moved = quota.window_for("day", now=after, zone_name="America/Los_Angeles", previous=_bucket(first))
    assert moved.start == first.end, "no overlap with the window already used"
    assert moved.end - moved.start >= quota.MIN_WINDOW["day"]
    assert moved.window_id.endswith("@America/Los_Angeles")


def test_hopping_zones_never_yields_more_than_one_window_a_day():
    zones = ["Pacific/Kiritimati", "Pacific/Pago_Pago", "Asia/Tokyo", "America/New_York", "Pacific/Kiritimati"]
    now, previous, starts = datetime(2026, 10, 1, tzinfo=UTC), None, []
    for step in range(60):
        window = quota.window_for("day", now=now, zone_name=zones[step % len(zones)], previous=previous)
        if previous is None or window.window_id != previous["window_id"]:
            starts.append(window.start)
        previous = _bucket(window)
        now += timedelta(hours=3)
    span_days = (now - datetime(2026, 10, 1, tzinfo=UTC)).total_seconds() / 86400
    assert len(starts) <= span_days / (23 / 24) + 1, "each window lasts at least 23 hours"
    assert all(b - a >= quota.MIN_WINDOW["day"] for a, b in zip(starts, starts[1:], strict=False))


def test_the_zone_is_the_requests_then_the_last_windows_then_utc():
    assert quota._zone_for(None) == "UTC"
    assert quota._zone_for({"window_id": "D:2026-10-09@Asia/Tokyo"}) == "Asia/Tokyo"
    with quota.request_facts(timezone="Europe/Paris"):
        assert quota._zone_for({"window_id": "D:2026-10-09@Asia/Tokyo"}) == "Europe/Paris"
    assert not quota.valid_zone("Mars/Olympus") and not quota.valid_zone("../etc") and quota.valid_zone("UTC")


# ------------------------------------------------------------ operation id --

def test_operation_ids_are_scoped_by_incarnation_and_meter_and_sensitive_to_the_body():
    base = dict(incarnation="i1", meter="writing.review", key="k", request_digest="d")
    one = quota.operation_id(**base)
    assert one.startswith("q1:") and len(one) <= 200
    assert quota.operation_id(**base) == one
    assert quota.operation_id(**{**base, "incarnation": "i2"}) != one
    assert quota.operation_id(**{**base, "meter": "orena.message"}) != one
    assert quota.operation_id(**{**base, "request_digest": "e"}) != one
    assert quota.operation_id(**{**base, "key": "k2"}) != one


# --------------------------------------------------------------- admission --

def test_exhausted_is_429_with_the_bucket_truth_and_retry_after():
    repository = enforced_runtime()
    for n in range(2):
        with quota.admit("writing.review", request_digest=f"r{n}") as ticket:
            ticket.dispatch("p")
            ticket.settle(1)
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="r3"):
            pytest.fail("no provider work when exhausted")
    error = refused.value
    assert error.status_code == 429
    assert error.detail["category"] == "quota_exhausted" and error.detail["retryable"] is False
    context = error.detail["context"]
    assert {k: context[k] for k in ("feature", "used", "limit", "unit", "window", "plan", "upgrade")} == {
        "feature": "writing.review", "used": 2, "limit": 2, "unit": "review", "window": "month",
        "plan": "free", "upgrade": "#/plan/pricing"}
    assert context["resets_at"] == "2026-11-01T00:00:00Z"
    assert int(error.headers["Retry-After"]) == int((datetime(2026, 11, 1, tzinfo=UTC) - datetime(2026, 10, 9, 12, 0, tzinfo=UTC)).total_seconds())
    assert sum(b["consumed"] for b in repository.buckets.values()) == 2


def test_an_exception_after_dispatch_settles_zero_and_before_dispatch_releases():
    repository = enforced_runtime()
    with pytest.raises(RuntimeError):
        with quota.admit("writing.review", request_digest="a") as ticket:
            ticket.dispatch("p")
            raise RuntimeError("provider failed")
    with pytest.raises(RuntimeError):
        with quota.admit("writing.review", request_digest="b"):
            raise RuntimeError("before the provider")
    assert "settle:0" in repository.calls and "release" in repository.calls
    assert [b["consumed"] + b["reserved"] for b in repository.buckets.values()] == [0]


def test_the_same_idempotency_key_and_body_is_one_operation():
    repository = enforced_runtime()
    with quota.request_facts(idempotency_key="press-1"):
        with quota.admit("writing.review", request_digest="same") as ticket:
            ticket.settle(1)
        with pytest.raises(HTTPException) as again:
            with quota.admit("writing.review", request_digest="same"):
                pass
    assert again.value.status_code == 409 and again.value.detail["category"] == "operation_finished"
    assert sum(b["consumed"] for b in repository.buckets.values()) == 1


def test_a_store_error_is_503_and_a_catalogue_error_is_503():
    class Broken(FakeQuotaRepository):
        def latest_buckets(self, *a, **k):
            raise RuntimeError("connection refused")

    enforced_runtime(repository=Broken())
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="x"):
            pass
    assert refused.value.status_code == 503 and refused.value.detail["context"]["reason"] == "store"

    enforced_runtime()
    configure_plan_store(MemorySettings(fail=True))
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="y"):
            pass
    assert refused.value.status_code == 503 and refused.value.detail["context"]["reason"] == "catalogue"


def test_a_disabled_entitlement_is_403_feature_not_in_plan():
    stored = {"version": 2, "plans": [
        {"id": plan_id, "prices": {}, "entitlements": [{"key": "writing.review", "enabled": plan_id != "free", "limit": 2}]}
        for plan_id in ("free", "plus", "pro")]}
    configure_plan_store(MemorySettings({catalog.PLAN_SETTING_KEY: {"value": stored, "updated_at": "t"}}))
    enforced_runtime()
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="x"):
            pass
    assert refused.value.status_code == 403 and refused.value.detail["category"] == "feature_not_in_plan"


def test_usage_reads_the_buckets_and_is_unavailable_never_zero():
    repository = enforced_runtime()
    with quota.admit("writing.review", request_digest="x") as ticket:
        ticket.settle(1)
    usage = quota.usage_for("legacy", catalog.FREE)  # the request-context account admit() metered
    assert usage["writing.review"]["state"] == "known" and usage["writing.review"]["used"] == 1
    assert usage["writing.review"]["resets_at"] == "2026-11-01T00:00:00Z"
    assert "orena.message" not in usage, "a meter not enforced is not metered"

    class Broken(FakeQuotaRepository):
        def latest_buckets(self, *a, **k):
            raise RuntimeError("down")

    enforced_runtime(repository=Broken())
    assert quota.usage_for("u", catalog.FREE) == {"writing.review": {"state": "unavailable"}}
    assert repository is not None


def test_the_reconciler_settles_abandoned_dispatched_work_and_releases_the_rest():
    repository = enforced_runtime()
    for name in ("dispatched", "reserved"):
        repository.reservations[name] = {"key": ("i", "writing.review", "w"), "units": 1, "state": name,
                                          "updated_at": datetime.now(UTC) - timedelta(hours=1)}
    repository.buckets[("i", "writing.review", "w")] = {"consumed": 0, "reserved": 2, "window_end": NOW}
    done = quota.reconcile_once(repository)
    assert done == {"settled": 1, "released": 1}
    assert repository.buckets[("i", "writing.review", "w")] == {"consumed": 1, "reserved": 0, "window_end": NOW}, \
        "abandoned dispatched work is charged what was reserved (human default, ABANDONED_SETTLES)"


# ------------------------------------------------------------------ routes --

@pytest.fixture()
def rooms(monkeypatch, tmp_path):
    import app as app_module
    from writing_coach.persistence.learning_repository import SQLiteLearningRepository

    client = TestClient(app_module.app)
    client.__enter__()
    repository = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
    repository.initialize()
    monkeypatch.setattr(app_module, "_learning_repository", repository)
    calls: list[str] = []

    def evaluator(payload):
        calls.append("evaluate")
        return {"grammar": 50.0, "vocabulary": 55.0, "coherence": 60.0, "task_achievement": 58.0, "naturalness": 52.0,
                "cefr_estimate": "B1", "summary_vi": "ok", "strengths_vi": [], "strength_evidence": [],
                "priorities_vi": [], "errors": [], "schema_version": "writing-evaluation-v2"}

    def improver(payload):
        calls.append("improve")
        return {"corrected_text": payload.text}

    monkeypatch.setattr(app_module, "evaluate_with_ai", evaluator)
    monkeypatch.setattr(app_module, "improve_with_ai", improver)
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", False)
    monkeypatch.setattr(app_module, "get_learner_profile", lambda *a, **k: {"support_language": "vi"})
    app_module._review_in_flight.clear()
    try:
        yield client, calls, app_module
    finally:
        client.__exit__(None, None, None)


TEXT = ("Hi Anna, I want to telling you about my last week. I go to the Da Nang office for a meeting with a "
        "customer and I dont finished the report.")


def _evaluate(client, text=TEXT, **headers):
    return client.post("/api/evaluate", json={"prompt": "Email", "text": text, "learning_language": "en"}, headers=headers)


def _improve(client, text=TEXT):
    return client.post("/api/improve", json={"text": text, "mode": "polish"})


def test_switch_off_changes_nothing_in_the_rooms(rooms):
    client, calls, _app = rooms
    quota.configure_quota(settings=MemorySettings(), env={})
    assert _evaluate(client).status_code == 200
    assert _improve(client).status_code == 200
    assert calls == ["evaluate", "improve"]
    commerce = client.get("/api/product/commerce").json()
    assert commerce["features"]["writing.review"]["usage_state"] == "not_metered"
    assert commerce["features"]["writing.review"]["used"] is None


def test_on_with_sqlite_refuses_before_the_provider(rooms):
    client, calls, _app = rooms
    quota.configure_quota(settings=MemorySettings(), env={quota.FLAG: "on", quota.METERS_FLAG: "writing.review"},
                          reason="no_postgresql")
    answer = _evaluate(client)
    assert answer.status_code == 503 and answer.json()["detail"]["category"] == "quota_unavailable"
    assert _improve(client).status_code == 503
    assert calls == [], "no provider call without a store to meter it"


def test_exhausted_rooms_answer_429_and_never_call_the_provider(rooms):
    client, calls, _app = rooms
    repository = enforced_runtime(clock=lambda: datetime.now(UTC))
    assert _evaluate(client, TEXT).status_code == 200
    assert _improve(client).status_code == 200
    assert calls == ["evaluate", "improve"]
    # A stored identical review is served from the store: no AI call, no charge.
    reused = _evaluate(client, TEXT)
    assert reused.status_code == 200 and reused.json()["reused"] is True
    assert calls == ["evaluate", "improve"]
    refused = _evaluate(client, TEXT + " And one more sentence today.")
    assert refused.status_code == 429
    assert refused.json()["detail"]["category"] == "quota_exhausted"
    assert int(refused.headers["Retry-After"]) > 0
    improve_refused = _improve(client)
    assert improve_refused.status_code == 429, "a refusal is never turned into the improve route's 502"
    assert calls == ["evaluate", "improve"], "the provider is not called once the plan is exhausted"
    assert sum(b["consumed"] for b in repository.buckets.values()) == 2
    commerce = client.get("/api/product/commerce").json()["features"]["writing.review"]
    assert (commerce["usage_state"], commerce["used"], commerce["limit"], commerce["remaining"]) == ("known", 2, 2, 0)
    assert commerce["entitlement_state"] == "exhausted"


def test_a_provider_failure_and_the_local_fallback_cost_nothing(rooms, monkeypatch):
    client, calls, app_module = rooms
    repository = enforced_runtime(clock=lambda: datetime.now(UTC))
    from writing_coach.ai.base import AIProviderError

    def failing(payload):
        calls.append("evaluate")
        raise AIProviderError("bad")

    monkeypatch.setattr(app_module, "evaluate_with_ai", failing)
    assert _evaluate(client).status_code == 502
    monkeypatch.setattr(app_module, "ALLOW_FALLBACK", True)
    assert _evaluate(client, TEXT + " Another try.").status_code == 200, "the local heuristic answers"
    assert calls == ["evaluate", "evaluate"]
    assert sum(b["consumed"] for b in repository.buckets.values()) == 0
    assert sum(b["reserved"] for b in repository.buckets.values()) == 0


def test_local_mode_reads_the_plan_of_the_metered_account():
    """With authentication off, the product reads and enforcement both key by the request context's account."""
    import writing_coach.product.api as product_api
    from writing_coach.core.request_context import USER_KEY_CTX

    if product_api.AUTH_ENABLED:
        pytest.skip("authentication is on in this environment")
    token = USER_KEY_CTX.set("legacy")
    try:
        assert product_api.current_user_key(object()) == "legacy"
    finally:
        USER_KEY_CTX.reset(token)


def test_admin_quota_routes_switch_enforcement(monkeypatch):
    from fastapi import FastAPI

    import writing_coach.product.api as product_api

    settings = MemorySettings()
    quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(),
                          plan_for=lambda *a, **k: catalog.FREE, settings=settings, env={})
    monkeypatch.setattr(product_api, "require_admin", lambda request: {"google_sub": "a", "email": "a@x.test"})
    api = FastAPI()
    api.include_router(product_api.router)
    client = TestClient(api)
    assert client.get("/api/product/admin/quota").json()["state"] == "off"
    on = client.put("/api/product/admin/quota", json={"enabled": True, "meters": ["writing.review"]})
    assert on.status_code == 200 and on.json()["state"] == "enforced"
    assert settings.rows[quota.SETTING_KEY]["value"] == {"enabled": True, "meters": ["writing.review"]}
    assert client.put("/api/product/admin/quota", json={"enabled": True, "meters": ["languages.target"]}).status_code == 422


# ------------------------------------------- review of #116: the switch fails closed (P2-1) --

def _switch_with(settings, env):
    quota.configure_quota(repository=FakeQuotaRepository(), incarnations=FakeIncarnations(),
                          plan_for=lambda user_key, strict=False: catalog.plan_by_id("free", strict=strict),
                          settings=settings, env=env)


def _refused_with_503():
    with pytest.raises(HTTPException) as refused:
        with quota.admit("writing.review", request_digest="x"):
            pytest.fail("no provider work when the switch is unknown")
    assert refused.value.status_code == 503 and refused.value.detail["category"] == "quota_unavailable"
    return refused.value.detail["context"]["reason"]


def test_env_off_is_off_even_when_the_setting_cannot_be_read():
    _switch_with(MemorySettings(fail=True), {quota.FLAG: "off"})
    assert quota.switch()["state"] == "off"
    with quota.admit("writing.review", request_digest="x") as ticket:
        assert ticket is quota.NULL_TICKET


def test_env_on_without_a_meter_is_a_503_not_a_silent_off():
    _switch_with(MemorySettings(), {quota.FLAG: "on"})
    state = quota.switch()
    assert (state["state"], state["reason"], state["meters"]) == ("unavailable", "no_meters", list(quota.WIRED_METERS))
    assert _refused_with_503() == "no_meters"
    _switch_with(MemorySettings(fail=True), {quota.FLAG: "on"})
    assert _refused_with_503() == "switch_unreadable"


def test_env_on_takes_its_meters_from_the_setting_when_the_env_lists_none():
    _switch_with(MemorySettings({quota.SETTING_KEY: {"value": {"enabled": False, "meters": ["writing.review"]}}}),
                 {quota.FLAG: "on"})
    assert quota.switch()["state"] == "enforced", "the environment's on wins over the setting's enabled"


def test_an_unreadable_setting_in_a_fresh_worker_fails_closed():
    _switch_with(MemorySettings(fail=True), {})
    state = quota.switch()
    assert (state["state"], state["reason"]) == ("unavailable", "switch_unreadable")
    assert _refused_with_503() == "switch_unreadable"
    assert quota.usage_for("legacy", catalog.FREE) == {key: {"state": "unavailable"} for key in quota.WIRED_METERS}


def test_an_unreadable_setting_after_a_good_read_keeps_the_last_value():
    settings = MemorySettings({quota.SETTING_KEY: {"value": {"enabled": True, "meters": ["writing.review"]}}})
    _switch_with(settings, {})
    assert quota.switch()["state"] == "enforced"
    settings.fail = True
    quota._clear_switch_cache()
    assert quota.switch()["state"] == "enforced"


def test_nothing_stored_and_no_env_is_off():
    _switch_with(MemorySettings(), {})
    assert quota.switch()["state"] == "off"


# --------------------------------- review of #116: /api/improve keeps a dispatch refusal's status (P2-2) --

@pytest.mark.parametrize("refusal, status, category", [("denied", 403, "account_deleted"),
                                                       ("raise", 503, "quota_unavailable")])
def test_a_refusal_at_dispatch_is_not_reported_as_502(rooms, refusal, status, category):
    client, calls, _app = rooms

    class Refusing(FakeQuotaRepository):
        def dispatch(self, *, operation_id, dispatch_ref=None):
            if refusal == "raise":
                raise RuntimeError("store down at dispatch")
            return {"status": "denied", "reason": "incarnation_deleted"}

    repository = enforced_runtime(repository=Refusing(), clock=lambda: datetime.now(UTC))
    answer = _improve(client)
    assert answer.status_code == status and answer.json()["detail"]["category"] == category
    assert calls == [], "the provider is not called"
    assert sum(b["reserved"] + b["consumed"] for b in repository.buckets.values()) == 0, "the reservation is released"
