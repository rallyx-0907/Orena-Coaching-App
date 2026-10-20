import copy

import pytest

from writing_coach.product import catalog
from writing_coach.product.catalog import (
    FREE,
    PLUS,
    PREMIUM,
    PRO,
    PlanCatalogInvalid,
    configure_plan_store,
    current_plans,
    plan_by_id,
    save_catalog,
    validate_catalog,
)


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def get_setting(self, key):
        return copy.deepcopy(self.rows.get(key))

    saves = 0
    audits = None

    def set_setting(self, key, value, *, updated_by="", expected_updated_at=..., audit=None):
        from writing_coach.persistence.platform_repository import SettingConflict

        stored = (self.rows.get(key) or {}).get("updated_at")
        if expected_updated_at is not ... and expected_updated_at != stored:
            raise SettingConflict(key)
        self.saves += 1
        self.audits = (self.audits or []) + [audit]
        self.rows[key] = {"value": copy.deepcopy(value), "updated_at": f"2026-10-09T10:00:{self.saves:02d}+00:00", "updated_by": updated_by}
        return copy.deepcopy(self.rows[key])


@pytest.fixture(autouse=True)
def no_store():
    configure_plan_store(None)
    yield
    configure_plan_store(None)


def document(**changes):
    plans = [plan.as_dict() for plan in (FREE, PLUS, PRO)]
    for row in plans:
        row.pop("name"), row.pop("description"), row.pop("price_label"), row.pop("rank")
        row.update(changes.get(row["id"], {}))
    return {"version": 2, "plans": plans}


def test_three_plans_in_rank_order():
    assert [plan.id for plan in current_plans().values()] == ["free", "plus", "pro"]
    assert [plan.rank for plan in current_plans().values()] == [0, 1, 2]
    assert plan_by_id("unknown").id == "free"


def test_premium_is_pro_for_stored_subscriptions():
    assert PREMIUM is PRO
    assert plan_by_id("premium").id == "pro"
    assert plan_by_id("Premium").entitlement_map()["writing.review"].limit == 50


def test_prices_follow_the_design_tiers():
    assert FREE.prices["monthly"] == {"USD": 0, "VND": 0}
    assert PLUS.prices["monthly"] == {"USD": 9.99, "VND": 199000}
    assert PLUS.prices["yearly"] == {"USD": 79.99, "VND": 1590000}
    assert PRO.prices["monthly"] == {"USD": 19.99, "VND": 399000}
    assert PRO.prices["yearly"] == {"USD": 159.99, "VND": 3190000}


def test_the_meters_are_the_designs_pricing():
    """D-161: the design's BILL_PLANS `lim` - messages/day, reviews/month, minutes (stored as seconds), languages."""
    free, plus, pro = (plan.entitlement_map() for plan in (FREE, PLUS, PRO))
    assert list(free) == ["orena.message", "writing.review", "pronunciation.audio", "media.import", "languages.target",
                          "word.assist", "reading.assist", "writing.task", "orena.voice", "media.tools_weekly",
                          "progress.weekly_report"]
    # D-248 (MV2-1): Free looks words up on 3 videos a week; Plus and Pro have the full media tools.
    assert [m["media.tools_weekly"].limit for m in (free, plus, pro)] == [3, 10_000, 10_000]
    assert free["media.tools_weekly"].window == "week"
    # Voice chat with Orena: Plus and Pro only (owner, 2026-10-19).
    assert [m["orena.voice"].enabled for m in (free, plus, pro)] == [False, True, True]
    assert [m["orena.message"].limit for m in (free, plus, pro)] == [20, 200, 1000]
    assert [m["writing.review"].limit for m in (free, plus, pro)] == [2, 10, 50]
    assert [m["pronunciation.audio"].limit for m in (free, plus, pro)] == [300, 1800, 7200]
    assert [m["media.import"].limit for m in (free, plus, pro)] == [900, 7200, 36000]
    assert [m["languages.target"].limit for m in (free, plus, pro)] == [1, 2, 2]
    assert free["orena.message"].window == "day" and free["writing.review"].window == "month"
    assert free["languages.target"].window is None
    assert free["orena.message"].params == {"voice_seconds_per_message": 60}
    for gone in ("writing.evaluate", "dictionary.lookup", "vocabulary.save", "analytics.advanced"):
        assert gone not in free, "features the design does not promise are not plan entitlements"
    row = free["pronunciation.audio"].as_dict()
    assert (row["unit"], row["display_unit"], row["scale"], row["monthly_limit"]) == ("second", "minute", 60, 300)
    assert free["orena.message"].as_dict()["monthly_limit"] is None, "the native field names only monthly limits"


def test_the_semantic_ai_meters_are_daily_requests_with_the_approved_bootstrap_limits():
    """PR-MON-7B1 (H7-3, D-MON-025): requests per day, Free/Plus/Pro, in the catalogue - defaults an admin edits."""
    from writing_coach.billing.funding import NEW_METER_UNITS
    from writing_coach.product.catalog import METERS

    free, plus, pro = (plan.entitlement_map() for plan in (FREE, PLUS, PRO))
    assert [m["word.assist"].limit for m in (free, plus, pro)] == [30, 300, 1500]
    assert [m["reading.assist"].limit for m in (free, plus, pro)] == [10, 100, 500]
    assert [m["writing.task"].limit for m in (free, plus, pro)] == [5, 30, 100]
    for key in ("word.assist", "reading.assist", "writing.task"):
        meter = METERS[key]
        assert (meter.window, meter.unit, meter.display_unit, meter.scale) == ("day", "request", "request", 1)
        assert meter.unit == NEW_METER_UNITS[key], "the frozen H-2 unit"
        assert free[key].enabled and free[key].as_dict()["monthly_limit"] is None


def test_the_semantic_ai_meters_are_wired_but_never_credit_funded():
    """PR-MON-7B2a: wired (enforceable when the switch lists them, reconciled as request-bound meters) and still never
    credit-funded."""
    from writing_coach.billing.funding import CREDIT_ELIGIBLE_V1
    from writing_coach.product import quota

    for key in ("word.assist", "reading.assist", "writing.task"):
        assert key in quota.WIRED_METERS and key in quota.ENFORCEABLE and key in quota.SYNC_METERS
        assert key not in CREDIT_ELIGIBLE_V1


def test_voice_is_a_monthly_meter_with_the_d248_limits():
    """D-248 (MV2-6a): `orena.voice` is seconds per month shown in minutes; Plus 6000 s (about 100 min), Pro 18000 s;
    Free stays off."""
    from datetime import UTC, datetime

    from writing_coach.product import quota
    from writing_coach.product.catalog import METERS

    meter = METERS["orena.voice"]
    assert (meter.window, meter.unit, meter.display_unit, meter.scale) == ("month", "second", "minute", 60)
    voice = [plan.entitlement_map()["orena.voice"] for plan in (FREE, PLUS, PRO)]
    assert [item.enabled for item in voice] == [False, True, True]
    assert [item.limit for item in voice[1:]] == [6000, 18000]
    row = voice[1].as_dict()
    assert (row["window"], row["monthly_limit"]) == ("month", 6000)
    # A monthly meter's window ends (its `resets_at`) at 00:00 on the 1st of the next month - the catalogue's window, read
    # by the quota's window. Voice's own counting moves to it in the Intelligence lane's plan_features change.
    window = quota.window_for(meter.window, now=datetime(2026, 10, 21, 9, tzinfo=UTC), zone_name="UTC", previous=None)
    assert window.end == datetime(2026, 11, 1, tzinfo=UTC)
    december = quota.window_for(meter.window, now=datetime(2026, 12, 31, 23, tzinfo=UTC), zone_name="UTC", previous=None)
    assert december.end == datetime(2027, 1, 1, tzinfo=UTC)


def test_the_weekly_report_is_an_on_off_plan_feature():
    """D-248 (MV2-6a): `progress.weekly_report` - Free off, Plus and Pro on; no window and no limit."""
    from writing_coach.product.catalog import METERS

    meter = METERS["progress.weekly_report"]
    assert meter.on_off is True and meter.window is None
    report = [plan.entitlement_map()["progress.weekly_report"] for plan in (FREE, PLUS, PRO)]
    assert [item.enabled for item in report] == [False, True, True]
    assert all(item.limit is None for item in report)


def test_an_admin_turns_the_weekly_report_on_and_off_but_never_gives_it_a_limit():
    store = MemoryStore()
    configure_plan_store(store)
    edited = document()
    for item in edited["plans"][0]["entitlements"]:
        if item["key"] == "progress.weekly_report":
            item["enabled"] = True
    save_catalog(edited, updated_by="admin")
    assert plan_by_id("free").entitlement_map()["progress.weekly_report"].enabled is True
    with pytest.raises(PlanCatalogInvalid, match="on or off"):
        validate_catalog(document(plus={"entitlements": [{"key": "progress.weekly_report", "enabled": True, "limit": 1}]}))


def test_a_stored_voice_placeholder_reads_as_the_plans_default_everywhere():
    """A voice limit under a minute (the D-236 on/off placeholder) reads as that plan's default in the catalogue itself,
    so Admin's editor, Plans and enforcement all see the same figure (no client-side constant)."""
    store = MemoryStore()
    configure_plan_store(store)
    stored = document()
    for row in stored["plans"]:
        for item in row["entitlements"]:
            if item["key"] == "orena.voice" and row["id"] != "free":
                item["limit"] = 1
    save_catalog(stored, updated_by="admin")
    assert [plan_by_id(plan).entitlement_map()["orena.voice"].limit for plan in ("plus", "pro")] == [6000, 18000]


def _stored_voice(store, limit, **window):
    """A saved catalogue whose voice limits are `limit`, saved under `window` (none: a document from before D-248)."""
    stored = document()
    for row in stored["plans"]:
        for item in row["entitlements"]:
            item.pop("window", None)
            if item["key"] == "orena.voice":
                item.update({"limit": limit, **window})
    store.rows[catalog.PLAN_SETTING_KEY] = {"value": stored, "updated_at": "2026-10-19T10:00:00+00:00", "updated_by": "a"}
    configure_plan_store(store)


def test_a_voice_limit_saved_per_day_is_not_read_as_a_month():
    """Review of #477, P1: a catalogue saved before D-248 holds `orena.voice` 900 (15 minutes a DAY). Once the meter is
    monthly it must not become 15 minutes a month: the built-in value applies and the Admin view names the stale limit.
    The stored document is not changed."""
    for window in ({"window": "day"}, {}):  # saved under "day", or with no window (a document from before this build)
        store = MemoryStore()
        _stored_voice(store, 900, **window)
        plans = current_plans(strict=True)
        assert [plans[plan].entitlement_map()["orena.voice"].limit for plan in ("plus", "pro")] == [6000, 18000]
        record = store.get_setting(catalog.PLAN_SETTING_KEY)
        assert catalog.stale_limits(record) == [  # Free's voice is off: nothing it limits, nothing to report
            {"plan": plan, "key": "orena.voice", "limit": 900, "saved_window": "day", "window": "month"}
            for plan in ("plus", "pro")]
        assert [item for row in record["value"]["plans"] for item in row["entitlements"]
                if row["id"] == "plus" and item["key"] == "orena.voice"][0]["limit"] == 900, "stored data untouched"


def test_a_voice_limit_saved_per_month_is_honoured_and_a_save_stamps_the_window():
    store = MemoryStore()
    _stored_voice(store, 4500, window="month")
    assert plan_by_id("plus", strict=True).entitlement_map()["orena.voice"].limit == 4500
    assert catalog.stale_limits(store.get_setting(catalog.PLAN_SETTING_KEY)) == []
    # An administrator's save records the window each limit was set for, so a later window change is detected.
    edited = document(plus={"entitlements": [{"key": "orena.voice", "enabled": True, "limit": 3000}]})
    save_catalog(edited, updated_by="admin")
    saved = store.get_setting(catalog.PLAN_SETTING_KEY)["value"]
    voice = [item for row in saved["plans"] for item in row["entitlements"] if row["id"] == "plus" and item["key"] == "orena.voice"]
    assert voice == [{"key": "orena.voice", "enabled": True, "limit": 3000, "params": {}, "window": "month"}]
    assert plan_by_id("plus").entitlement_map()["orena.voice"].limit == 3000


def test_other_meters_saved_without_a_window_keep_their_limits():
    """Only a meter whose window changed is affected: a pre-D-248 document's other limits still apply."""
    store = MemoryStore()
    _stored_voice(store, 900)
    for row in store.rows[catalog.PLAN_SETTING_KEY]["value"]["plans"]:
        for item in row["entitlements"]:
            if row["id"] == "plus" and item["key"] == "writing.review":
                item["limit"] = 12
    assert plan_by_id("plus", strict=True).entitlement_map()["writing.review"].limit == 12


def test_the_admin_view_reports_a_stale_limit(monkeypatch):
    import writing_coach.product.api as product_api

    store = MemoryStore()
    _stored_voice(store, 900, window="day")
    assert product_api._admin_catalog()["stale_limits"] == [
        {"plan": plan, "key": "orena.voice", "limit": 900, "saved_window": "day", "window": "month"} for plan in ("plus", "pro")]


def test_a_stored_catalogue_without_the_new_meters_reads_their_defaults():
    """A catalogue saved before PR-MON-7B1 (version 2, no new keys) still reads: the new meters take the code
    defaults, the stored limits stay."""
    store = MemoryStore()
    configure_plan_store(store)
    old = document()
    new_keys = {"word.assist", "reading.assist", "writing.task"}
    for row in old["plans"]:
        row["entitlements"] = [item for item in row["entitlements"] if item["key"] not in new_keys]
        for item in row["entitlements"]:
            if row["id"] == "plus" and item["key"] == "writing.review":
                item["limit"] = 12
    save_catalog(old, updated_by="admin")
    plus = plan_by_id("plus").entitlement_map()
    assert plus["writing.review"].limit == 12 and plus["word.assist"].limit == 300


def test_an_admin_edits_a_semantic_ai_meter_like_any_other_limit():
    store = MemoryStore()
    configure_plan_store(store)
    edited = document()
    for item in edited["plans"][0]["entitlements"]:
        if item["key"] == "word.assist":
            item["limit"] = 40
    save_catalog(edited, updated_by="admin")
    assert plan_by_id("free").entitlement_map()["word.assist"].limit == 40


def test_an_admin_change_applies_from_the_moment_it_is_saved():
    store = MemoryStore()
    configure_plan_store(store)
    assert plan_by_id("plus").entitlement_map()["writing.review"].limit == 10
    new_plus = {
        "prices": {"monthly": {"USD": 7.5, "VND": 150000}, "yearly": {"USD": 70, "VND": 1400000}},
        "entitlements": [{"key": "writing.review", "enabled": True, "limit": 12},
                         {"key": "orena.message", "enabled": True, "limit": 250, "params": {"voice_seconds_per_message": 30}}],
    }
    saved = save_catalog(document(plus=new_plus), updated_by="admin@example.test")
    assert saved["updated_by"] == "admin@example.test"
    plus = plan_by_id("plus")
    assert plus.prices["monthly"] == {"USD": 7.5, "VND": 150000}
    assert plus.entitlement_map()["writing.review"].limit == 12
    assert plus.entitlement_map()["orena.message"].params == {"voice_seconds_per_message": 30}
    # Untouched entitlements keep the code's defaults.
    assert plus.entitlement_map()["media.import"].limit == 7200
    assert plan_by_id("pro").prices == PRO.prices


def test_a_broken_stored_document_is_ignored_not_half_applied():
    store = MemoryStore()
    store.rows[catalog.PLAN_SETTING_KEY] = {"value": {"plans": "nope"}, "updated_at": "x", "updated_by": ""}
    configure_plan_store(store)
    assert plan_by_id("plus").prices == PLUS.prices


def test_a_failing_store_falls_back_to_the_defaults():
    class Broken:
        def get_setting(self, key):
            raise RuntimeError("down")

    configure_plan_store(Broken())
    assert plan_by_id("pro").entitlement_map()["writing.review"].limit == 50


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"free": {"prices": {"monthly": {"USD": 1, "VND": 0}}}}, "Free has no price"),
        ({"plus": {"prices": {"monthly": {"USD": -1, "VND": 0}}}}, "between 0"),
        ({"plus": {"prices": {"monthly": {"USD": 1, "VND": 1.5}}}}, "whole number"),
        ({"plus": {"entitlements": [{"key": "writing.review", "enabled": True, "limit": 2.5}]}}, "whole number"),
        ({"plus": {"entitlements": [{"key": "writing.review", "enabled": True, "limit": None}]}}, "required"),
        ({"plus": {"entitlements": [{"key": "writing.evaluate", "enabled": True, "limit": 5}]}}, "unknown feature"),
        ({"plus": {"entitlements": [{"key": "made.up", "enabled": True, "limit": 5}]}}, "unknown feature"),
        ({"plus": {"entitlements": [{"key": "writing.review", "enabled": "yes", "limit": 5}]}}, "true or false"),
        ({"plus": {"entitlements": [{"key": "writing.review", "enabled": True, "limit": 5, "params": {"x": 1}}]}}, "unknown parameter"),
        ({"plus": {"entitlements": [{"key": "orena.message", "enabled": True, "limit": 5,
                                     "params": {"voice_seconds_per_message": 0}}]}}, "between 1"),
    ],
)
def test_validation_refuses_what_cannot_apply(changes, message):
    with pytest.raises(PlanCatalogInvalid, match=message):
        validate_catalog(document(**changes))


def test_validation_needs_exactly_the_three_plans():
    whole = document()
    with pytest.raises(PlanCatalogInvalid, match="Free, Plus and Pro"):
        validate_catalog({"version": 2, "plans": whole["plans"][:2]})
    with pytest.raises(PlanCatalogInvalid, match="Unknown plan"):
        validate_catalog({"version": 2, "plans": whole["plans"] + [{"id": "gold"}]})


def test_saving_without_a_store_is_an_error_not_a_silent_drop():
    with pytest.raises(RuntimeError):
        save_catalog(document())
    with pytest.raises(PlanCatalogInvalid):
        save_catalog({"plans": []}), "an invalid document is refused on its merits first"


def test_admin_routes_read_and_save_the_catalogue(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import writing_coach.product.api as product_api

    store = MemoryStore()
    configure_plan_store(store)
    monkeypatch.setattr(product_api, "require_admin", lambda request: {"google_sub": "admin-sub", "email": "admin@example.test"})
    app = FastAPI()
    app.include_router(product_api.router)
    client = TestClient(app)

    body = client.get("/api/product/admin/plans").json()
    assert [plan["id"] for plan in body["plans"]] == ["free", "plus", "pro"]
    assert body["source"] == "default"
    assert body["updated_at"] is None

    saved = client.put("/api/product/admin/plans", json=document(pro={"prices": {"monthly": {"USD": 25, "VND": 500000}, "yearly": {"USD": 200, "VND": 4000000}}}))
    assert saved.status_code == 200
    assert saved.json()["source"] == "stored"
    assert saved.json()["updated_by"] == "admin@example.test"
    assert plan_by_id("pro").prices["monthly"]["USD"] == 25

    refused = client.put("/api/product/admin/plans", json={"plans": []})
    assert refused.status_code == 422


def test_admin_routes_refuse_a_learner(monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    import writing_coach.product.api as product_api

    def deny(request):
        raise HTTPException(403, "Platform administrator access required")

    monkeypatch.setattr(product_api, "require_admin", deny)
    app = FastAPI()
    app.include_router(product_api.router)
    client = TestClient(app)
    assert client.get("/api/product/admin/plans").status_code == 403
    assert client.put("/api/product/admin/plans", json=document()).status_code == 403


def test_a_save_from_a_stale_page_is_refused(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import writing_coach.product.api as product_api

    configure_plan_store(MemoryStore())
    monkeypatch.setattr(product_api, "require_admin", lambda request: {"google_sub": "a", "email": "a@example.test"})
    app = FastAPI()
    app.include_router(product_api.router)
    client = TestClient(app)
    first = client.put("/api/product/admin/plans", json={**document(), "expected_updated_at": None})
    assert first.status_code == 200
    stamp = first.json()["updated_at"]
    assert client.put("/api/product/admin/plans", json={**document(), "expected_updated_at": None}).status_code == 409, "opened before the first save"
    assert client.put("/api/product/admin/plans", json={**document(), "expected_updated_at": stamp}).status_code == 200
