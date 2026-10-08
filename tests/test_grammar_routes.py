"""The grammar routes end to end on SQLite: admin import -> attest -> review -> publish -> learner API -> progress.

The real routers on a bare app (the Reading engine's route-test pattern), the real store, and the real SQLite learning
repository for `grammar_progress`. The guard, the session language and the audit sink are the only seams.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from tests.grammar_store_support import body, manifest, sqlite_engine, zip_package
from writing_coach import grammar_admin_api, grammar_api
from writing_coach.persistence.grammar_store_repository import GrammarStoreRepository
from writing_coach.persistence.learning_repository import SQLiteLearningRepository

ORIGIN = {"origin": "http://testserver"}


class World:
    def __init__(self, tmp_path):
        self.engine = sqlite_engine(tmp_path)
        self.store = GrammarStoreRepository(self.engine)
        self.progress = SQLiteLearningRepository(lambda: tmp_path / "writing.db")
        self.progress.initialize()
        self.language = "en"
        self.admin = True
        self.audits: list[tuple[str, dict]] = []

        def guard(_request):
            if not self.admin:
                raise HTTPException(403, "Platform administrator access required")
            return {"email": "admin@example.org"}

        grammar_admin_api.configure_grammar_admin(
            admin_guard=guard, store=self.store,
            audit=lambda action, **kw: self.audits.append((action, kw)))
        grammar_api.configure_grammar_api(self.store, self.progress, language=lambda: self.language)
        app = FastAPI()
        app.include_router(grammar_admin_api.router)
        app.include_router(grammar_api.router)
        self.client = TestClient(app)

    def upload(self, data: bytes, *, path: str = "/api/admin/grammar/imports", **form):
        return self.client.post(path, headers=ORIGIN, files={"upload": ("pkg.zip", data, "application/zip")}, data=form)

    def import_and_publish(self, bodies, **kw):
        m = manifest(bodies, **kw)
        response = self.upload(zip_package(m, bodies), package_hash=m["package_hash"],
                               rights_basis="orena_original", rights_attestation="Orena's own synthetic test text.")
        assert response.status_code == 201, response.text
        items = []
        for b in bodies:
            version = next(v for v in self.client.get(f"/api/admin/grammar/points/{b['id']}").json()["versions"]
                           if v["version"] == b["version"])
            assert self.client.post(f"/api/admin/grammar/versions/{version['id']}/review", headers=ORIGIN,
                                    json={"decision": "accept"}).status_code == 200
            items.append({"point_id": b["id"], "version_id": version["id"]})
        published = self.client.post("/api/admin/grammar/publish", headers=ORIGIN, json={"items": items, "attested": True})
        assert published.status_code == 200, published.text
        return items


@pytest.fixture(autouse=True)
def _restore_module_state():
    """Put back whatever the app wired into the module seams, so a later suite sees the app's own wiring."""
    saved = (grammar_admin_api._state, grammar_api._state)
    yield
    grammar_admin_api._state, grammar_api._state = saved


@pytest.fixture()
def world(tmp_path):
    w = World(tmp_path)
    yield w
    w.engine.dispose()


def test_unconfigured_store_answers_503(tmp_path):
    grammar_api.configure_grammar_api(None)
    grammar_admin_api.configure_grammar_admin(admin_guard=None)
    app = FastAPI()
    app.include_router(grammar_api.router)
    app.include_router(grammar_admin_api.router)
    client = TestClient(app)
    assert client.get("/api/grammar/v1/points").json()["detail"]["category"] == "grammar_store_unavailable"
    assert client.get("/api/admin/grammar/imports").status_code == 503


def test_admin_changes_need_the_guard_and_the_console_origin(world):
    data = zip_package(manifest([body("en.a")]), [body("en.a")])
    assert world.client.post("/api/admin/grammar/imports/validate",
                             files={"upload": ("p.zip", data, "application/zip")}).status_code == 403
    world.admin = False
    assert world.upload(data, path="/api/admin/grammar/imports/validate").status_code == 403
    world.admin = True
    response = world.upload(data, path="/api/admin/grammar/imports/validate")
    assert response.status_code == 200 and response.json()["ok"] and response.headers["cache-control"] == "no-store"
    assert world.client.get("/api/admin/grammar/imports").json()["batches"] == []  # the dry run wrote nothing


def test_import_receipts_idempotency_and_rejection(world):
    b = body("en.a")
    m = manifest([b])
    data = zip_package(m, [b])
    assert world.upload(data, package_hash="0" * 64).json()["detail"]["category"] == "grammar_package_hash_mismatch"
    first = world.upload(data, package_hash=m["package_hash"])
    assert first.status_code == 201 and first.json()["batch"]["counts"]["new"] == 1
    again = world.upload(data, package_hash=m["package_hash"])
    assert again.status_code == 200 and again.json() == {"already_imported": True, "batch": first.json()["batch"]}
    bad = zip_package(manifest([b], source_dirty=True), [b])
    rejected = world.upload(bad, package_hash=manifest([b], source_dirty=True)["package_hash"])
    assert rejected.status_code == 422 and rejected.json()["detail"]["category"] == "grammar_package_rejected"
    assert {row["status"] for row in world.client.get("/api/admin/grammar/imports").json()["batches"]} == {
        "imported", "rejected"}
    assert world.upload(b"not a zip").json()["detail"]["category"] == "grammar_package_unreadable"
    assert [a for a, _ in world.audits] == ["admin.grammar_import_imported", "admin.grammar_import_rejected"]


def test_publish_must_be_explicit_and_gated(world):
    b = body("en.a")
    m = manifest([b])
    world.upload(zip_package(m, [b]), package_hash=m["package_hash"])
    vid = world.client.get("/api/admin/grammar/points/en.a").json()["versions"][0]["id"]
    publish = "/api/admin/grammar/points/en.a/publish"
    assert world.client.post(publish, headers=ORIGIN, json={"version_id": vid}).json()["detail"]["category"] == \
        "grammar_publish_unattested"
    assert world.client.post(publish, headers=ORIGIN, json={"version_id": vid, "attested": True}).status_code == 409
    world.client.post(f"/api/admin/grammar/versions/{vid}/review", headers=ORIGIN, json={"decision": "accept"})
    refused = world.client.post(publish, headers=ORIGIN, json={"version_id": vid, "attested": True})
    assert refused.json()["detail"]["category"] == "grammar_rights_not_cleared"
    batch = world.client.get("/api/admin/grammar/imports").json()["batches"][0]["id"]
    assert world.client.post(f"/api/admin/grammar/imports/{batch}/rights", headers=ORIGIN,
                             json={"basis": "orena_original", "attestation": "Ours."}).status_code == 200
    assert world.client.post(publish, headers=ORIGIN, json={"version_id": vid, "attested": True}).status_code == 200
    assert world.client.get("/api/grammar/v1/points").json()["points"][0]["id"] == "en.a"


def test_learner_catalogue_point_etags_and_language_scope(world):
    world.import_and_publish([body("en.a", aliases=["a1-old"]), body("en.b", sequence=2)],
                             r5_map=[{"r5_id": "a1-old", "point_id": "en.a", "disposition": "replaced", "is_primary": True}])
    catalog = world.client.get("/api/grammar/v1/points")
    assert catalog.status_code == 200 and catalog.headers["etag"] == 'W/"en-1"'
    assert catalog.headers["cache-control"] == "private, no-cache"
    assert world.client.get("/api/grammar/v1/points", headers={"if-none-match": 'W/"en-1"'}).status_code == 304
    point = world.client.get("/api/grammar/v1/points/en.a")
    assert point.status_code == 200 and "catalog_revision" not in point.json()
    assert "source_refs" not in point.json()["point"]
    etag = point.headers["etag"]
    assert world.client.get("/api/grammar/v1/points/en.a", headers={"if-none-match": etag}).status_code == 304
    assert world.client.get("/api/grammar/v1/points/a1-old").json() == {"language": "en", "point": None,
                                                                         "redirect": "en.a"}
    assert world.client.get("/api/grammar/v1/points/en:grammar:v2:a1-old").json()["redirect"] == "en.a"
    assert world.client.get("/api/grammar/v1/points/nope").status_code == 404
    assert world.client.get("/api/grammar/v1/points/zh.le").json()["detail"]["category"] == "grammar_language_mismatch"
    world.language = "zh"
    assert world.client.get("/api/grammar/v1/points").json()["points"] == []
    world.language = "ja"
    assert world.client.get("/api/grammar/v1/points").status_code == 404
    world.language = "en"
    by_error = world.client.get("/api/grammar/v1/by-error", params={"error_tag": "tense_choice", "level": "A1"}).json()
    assert {p["grammar_id"] for p in by_error["points"]} <= {"en.a", "en.b"} and by_error["points"][0]["reason"]


def test_unpublish_takes_effect_on_the_next_request_with_a_new_revision(world):
    world.import_and_publish([body("en.a")])
    assert world.client.post("/api/admin/grammar/points/en.a/status", headers=ORIGIN,
                             json={"action": "unpublish"}).status_code == 200
    catalog = world.client.get("/api/grammar/v1/points", headers={"if-none-match": 'W/"en-1"'})
    assert catalog.status_code == 200 and catalog.headers["etag"] == 'W/"en-2"' and catalog.json()["points"] == []
    assert world.client.get("/api/grammar/v1/points/en.a").status_code == 404


def test_progress_is_one_write_rechecked_by_the_server_and_keeps_the_first_completion(world):
    world.import_and_publish([body("en.a")])
    assert world.client.put("/api/grammar/v1/progress/en.a", json={"answers": [0, 0]}).status_code == 422
    assert world.client.put("/api/grammar/v1/progress/en.a", json={"answers": [0, 9, None]}).status_code == 422
    first = world.client.put("/api/grammar/v1/progress/en.a", json={"answers": [0, 0, None]}).json()
    # The key is [0, 1, 0]: one right of three, computed by the server.
    assert first["last_quiz"]["correct"] == 1 and first["last_quiz"]["total"] == 3
    assert first["claim"] == "activity_evidence_not_mastery"
    again = world.client.put("/api/grammar/v1/progress/en.a", json={"answers": [0, 1, 0]}).json()
    assert again["last_quiz"]["correct"] == 3 and again["completed_at"] == first["completed_at"]
    kept = world.client.put("/api/grammar/v1/progress/en.a", json={}).json()
    assert kept["last_quiz"]["correct"] == 3  # a completion without answers never clears an earlier result
    listed = world.client.get("/api/grammar/v1/progress").json()["progress"]
    assert listed == [{"point_id": "en.a", "completed_at": first["completed_at"], "last_quiz": kept["last_quiz"],
                       "via": "own"}]
    assert world.client.put("/api/grammar/v1/progress/en.nope", json={}).status_code == 404
    assert world.client.delete("/api/grammar/v1/progress/en.a").json() == {"point_id": "en.a", "changed": True}
    assert world.client.get("/api/grammar/v1/progress").json()["progress"] == []


def test_r5_progress_reads_through_the_map_merged_needs_all_and_splits_do_not_inherit(world):
    def r(rid, pid, disp, primary):
        return {"r5_id": rid, "point_id": pid, "disposition": disp, "is_primary": primary}
    world.import_and_publish(
        [body("en.m", aliases=["a1-be", "a1-be-q"]), body("en.p", aliases=["a2-past"], sequence=2),
         body("en.s", r5_split=["a2-past"], sequence=3)],
        r5_map=[r("a1-be", "en.m", "merged", True), r("a1-be-q", "en.m", "merged", True),
                r("a2-past", "en.p", "split_primary", True), r("a2-past", "en.s", "split_secondary", False)])
    # Historical R5 rows, as the R5 route stored them (composite keys), are never rewritten.
    world.progress.set_grammar_completed("en:grammar:v2:a1-be", "2026-09-01T00:00:00+00:00")
    world.progress.set_grammar_completed("en:grammar:v2:a2-past", "2026-09-02T00:00:00+00:00")
    listed = {e["point_id"]: e for e in world.client.get("/api/grammar/v1/progress").json()["progress"]}
    assert set(listed) == {"en.p"}  # merged needs both; the split secondary inherits nothing
    assert listed["en.p"]["via"] == "r5" and listed["en.p"]["r5_ids"] == ["a2-past"]
    world.progress.set_grammar_completed("en:grammar:v1:a1-be-q", "2026-09-03T00:00:00+00:00")
    listed = {e["point_id"]: e for e in world.client.get("/api/grammar/v1/progress").json()["progress"]}
    assert set(listed) == {"en.m", "en.p"} and listed["en.m"]["completed_at"].startswith("2026-09-01")
    assert world.client.put("/api/grammar/v1/progress/a1-be", json={}).json()["detail"]["category"] == \
        "grammar_point_moved"  # writes never target an alias
    assert world.client.delete("/api/grammar/v1/progress/en.m").json()["changed"] is True
    assert "en:grammar:v2:a1-be" not in world.progress.completed_grammar_ids()


def test_admin_reads(world):
    world.import_and_publish([body("en.a", aliases=["r5-a"])],
                             r5_map=[{"r5_id": "r5-a", "point_id": "en.a", "disposition": "replaced", "is_primary": True}])
    point = world.client.get("/api/admin/grammar/points/en.a").json()
    assert [e["action"] for e in point["events"]] == ["imported", "accepted", "published"]
    preview = world.client.get(f"/api/admin/grammar/versions/{point['versions'][0]['id']}/preview").json()
    assert preview["point"]["id"] == "en.a" and "source_refs" not in preview["point"]
    assert world.client.get("/api/admin/grammar/r5-map", params={"language": "en"}).json()["rows"][0]["r5_id"] == "r5-a"
    assert world.client.get("/api/admin/grammar/coverage", params={"language": "en"}).json()["complete"] is True
    assert world.client.get("/api/admin/grammar/points", params={"language": "en", "status": "published"}).json()[
        "points"][0]["id"] == "en.a"
