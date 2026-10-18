"""#196: the rights of an existing source can be corrected, and the correction reaches new texts only.

A source's rights are copied onto each source item when it is ingested (the snapshot), so a correction does
not rewrite texts already in the library; it applies to what is ingested afterwards. No article status moves.
"""
# ruff: noqa: F811 - the imported `setup` fixture is used by name as a test argument
from __future__ import annotations

from tests.test_reading_engine_routes import ARTICLE, call, setup  # noqa: F401 - the route fixture

BASE = "/api/admin/reading/sources"
RIGHTS = {
    "automation_allowed": True,
    "can_republish": True,
    "can_adapt": True,
    "attribution_required": True,
    "license_note": "Public domain (US Government work), NASA",
}


def _source(setup, **extra):
    body = {"slug": "valley-news", "name": "Valley News", "source_type": "rss",
            "base_url": "https://example.com/feed", "languages": ["en"], **extra}
    return call(setup["admin"], "POST", BASE, json=body).json()


def test_the_rights_of_an_existing_source_can_be_corrected(setup):
    source = _source(setup, license_note="not cleared")
    response = call(setup["admin"], "POST", f"{BASE}/{source['id']}/rights", json=RIGHTS)
    assert response.status_code == 200
    assert response.json()["rights"] == RIGHTS
    assert setup["content"].get_source(source["id"])["rights"] == RIGHTS
    assert response.headers["cache-control"] == "no-store"


def test_an_unknown_source_is_a_404_and_extra_fields_are_refused(setup):
    missing = call(setup["admin"], "POST", f"{BASE}/00000000-0000-0000-0000-000000000000/rights", json=RIGHTS)
    assert missing.status_code == 404
    assert missing.json()["detail"]["category"] == "reading_source_not_found"
    source = _source(setup)
    assert call(setup["admin"], "POST", f"{BASE}/{source['id']}/rights",
                json={**RIGHTS, "state": "active"}).status_code == 422
    assert call(setup["admin"], "POST", f"{BASE}/{source['id']}/rights",
                json={**RIGHTS, "license_note": "x" * 2001}).status_code == 422


def test_only_an_administrator_from_this_site_may_change_rights(setup):
    source = _source(setup)
    url = f"{BASE}/{source['id']}/rights"
    assert call(setup["admin"], "POST", url, admin=False, json=RIGHTS).status_code == 403
    assert call(setup["admin"], "POST", url, origin="https://evil.example", json=RIGHTS).status_code == 403
    assert setup["content"].get_source(source["id"])["rights"]["license_note"] == ""


def test_the_change_is_audited_with_before_and_after(setup):
    source = _source(setup, license_note="not cleared")
    call(setup["admin"], "POST", f"{BASE}/{source['id']}/rights", json=RIGHTS)
    rows = [row for row in setup["audit"] if row["action"] == "admin.reading_source_rights"]
    assert len(rows) == 1 and rows[0]["entity_id"] == source["id"]


def test_turning_automation_off_stops_polling_and_keeps_the_source_approved(setup):
    source = _source(setup, automation_allowed=True)
    on = call(setup["admin"], "POST", f"{BASE}/{source['id']}", json={"state": "active", "polling_enabled": True})
    assert on.json()["polling_enabled"] is True
    off = call(setup["admin"], "POST", f"{BASE}/{source['id']}/rights", json={**RIGHTS, "automation_allowed": False})
    body = off.json()
    assert off.status_code == 200
    assert body["polling_enabled"] is False and body["state"] == "active"
    refused = call(setup["admin"], "POST", f"{BASE}/{source['id']}", json={"state": "active", "polling_enabled": True})
    assert refused.status_code == 422


def test_turning_automation_on_does_not_start_polling(setup):
    source = _source(setup)
    body = call(setup["admin"], "POST", f"{BASE}/{source['id']}/rights", json=RIGHTS).json()
    assert body["polling_enabled"] is False and body["state"] == "needs_review"


def _ingest_from(setup, source_id, text=ARTICLE):
    response = call(setup["admin"], "POST", "/api/admin/reading/jobs",
                    data={"kind": "text", "text": text, "title": "River", "language": "en", "source_id": source_id})
    assert response.status_code == 202
    return setup["engine"].process(setup["jobs"].claim("worker-1"))["article_id"]


def _licence(setup, article_id):
    detail = call(setup["admin"], "GET", f"/api/admin/reading/articles/{article_id}").json()
    return detail["source"]["rights"].get("license_note")


def test_the_correction_reaches_new_texts_and_leaves_ingested_ones_alone(setup):
    source = _source(setup, license_note="not cleared")
    call(setup["admin"], "POST", f"{BASE}/{source['id']}", json={"state": "active"})
    before = _ingest_from(setup, source["id"])
    status_before = call(setup["admin"], "GET", f"/api/admin/reading/articles/{before}").json()["status"]
    call(setup["admin"], "POST", f"{BASE}/{source['id']}/rights", json=RIGHTS)
    after = _ingest_from(setup, source["id"], ARTICLE + "A second paragraph keeps this text distinct. ")
    assert _licence(setup, before) == "not cleared"
    assert _licence(setup, after) == RIGHTS["license_note"]
    assert call(setup["admin"], "GET", f"/api/admin/reading/articles/{before}").json()["status"] == status_before
