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
    """D-160: the design's BILL_PLANS `lim` - messages/day, reviews/month, minutes (stored as seconds), languages."""
    free, plus, pro = (plan.entitlement_map() for plan in (FREE, PLUS, PRO))
    assert list(free) == ["orena.message", "writing.review", "pronunciation.audio", "media.import", "languages.target"]
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
