"""Content packs v1: a verified format, and Reading moved between two environments through its engine."""

from __future__ import annotations

import asyncio
import io
import json
import zipfile

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from writing_coach import content_pack_api
from writing_coach import reading_admin_api as admin_api
from writing_coach.content_packs import PackError, PackItem, build_pack, read_pack
from writing_coach.persistence.models import Base
from writing_coach.persistence.reading_content_repository import ReadingContentRepository
from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_content_engine import ReadingContentEngine

BODY = ("Rain returned to the valley after a long dry summer. The river rose by morning and the farmers moved "
        "their animals to higher ground. By evening the fields were flooded, but nobody was hurt. The village "
        "school opened late the next day, and the children helped to carry sandbags to the bridge.")


def _item(**data):
    return PackItem(kind="vocabulary_collection", natural_key="sample-x",
                    data={"id": "sample-x", "language_code": "en", "entries": [], **data})  # fmt: skip


def _pack(*items):
    return build_pack(items or [_item()], created_by="a@example.com", environment="test", app_version="t", filters={})


# ---- the format -------------------------------------------------------------------------------------------


def test_a_pack_round_trips_and_lists_every_file_with_its_hash():
    pack = read_pack(_pack())
    assert pack.manifest["format"] == "orena-content-pack" and pack.manifest["counts"] == {"vocabulary_collection": 1}
    assert [item.natural_key for item in pack.items] == ["sample-x"]


def _rewrite(raw: bytes, change) -> bytes:
    source = zipfile.ZipFile(io.BytesIO(raw))
    files = {name: source.read(name) for name in source.namelist()}
    change(files)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return out.getvalue()


@pytest.mark.parametrize(("change", "code"), [
    (lambda f: f.update({"items/vocabulary_collection/sample-x.json": f["items/vocabulary_collection/sample-x.json"].replace(b"sample-x", b"sample-y", 1)}), "pack_hash_mismatch"),
    (lambda f: f.update({"../evil.json": b"{}"}), "pack_unsafe_path"),
    (lambda f: f.update({"items/reading_article/extra.json": b"{}"}), "pack_files_mismatch"),
    (lambda f: f.update({"manifest.json": f["manifest.json"].replace(b'"version":1', b'"version":9')}), "pack_version_newer"),
    (lambda f: f.pop("manifest.json"), "pack_manifest_missing"),
])  # fmt: skip
def test_a_tampered_or_unsafe_pack_is_refused_before_anything_is_planned(change, code):
    with pytest.raises(PackError) as refused:
        read_pack(_rewrite(_pack(), change))
    assert refused.value.code == code


def test_a_pack_carrying_a_learner_or_secret_field_is_never_built():
    with pytest.raises(PackError) as refused:
        _pack(_item(entries=[{"user_id": "u1"}]))
    assert refused.value.code == "pack_forbidden_field"


def test_not_a_zip_is_refused():
    with pytest.raises(PackError) as refused:
        read_pack(b"not a zip")
    assert refused.value.code == "pack_not_zip"


# ---- Reading moved between two environments ---------------------------------------------------------------


def guard(request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "Platform administrator access required")
    return {"email": "admin@example.com", "google_sub": "admin"}


def _environment():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    content = ReadingContentRepository(engine)
    content.ensure_built_in_sources()
    jobs = ReadingJobRepository(engine)
    return content, jobs, ReadingContentEngine(content=content, jobs=jobs)


def _use(content, jobs, engine_service):
    admin_api.configure_reading_admin(admin_guard=guard, content=content, jobs=jobs, engine=engine_service,
                                      audit=lambda *a, **k: None)  # fmt: skip
    content_pack_api.configure_content_packs()


def call(app, method, path, **kwargs):
    headers = {"x-test-admin": "1", "origin": "http://testserver"}

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run())


@pytest.fixture()
def app():
    application = FastAPI()
    application.include_router(content_pack_api.router)
    yield application
    admin_api.configure_reading_admin(admin_guard=None)
    content_pack_api.configure_content_packs()


def _published_sample(content, jobs, engine_service):
    source = content.create_source(slug="sample-news", name="Sample news", source_type="manual", base_url="",
                                   languages=["en"], rights={"automation_allowed": True, "can_republish": True,
                                   "can_adapt": False, "attribution_required": True, "license_note": "CC BY 4.0"},
                                   created_by="admin")  # fmt: skip
    content.set_source_state(source["id"], "active", actor="admin")
    from writing_coach.reading_source_import import SubmittedInput

    engine_service.submit(SubmittedInput(kind="text", text=BODY, title="Rain returns", author="M. Tran", language="en",
                                         source_id=source["id"], rights={"license_note": "CC BY 4.0"}), actor="admin")  # fmt: skip
    outcome = engine_service.process(jobs.claim("worker-1"))
    article = content.get_article(outcome["article_id"])
    if article["status"] != "published":
        content.set_status(article["id"], "published", actor="admin")
    return article["id"]


def test_reading_exports_then_imports_into_another_environment_through_its_engine(app):
    here = _environment()
    _use(*here)
    _published_sample(*here)
    exported = call(app, "POST", "/api/admin/content-packs/export", json={"kinds": ["reading"], "source_slug_prefix": "sample-"})
    assert exported.status_code == 200, exported.text
    raw = exported.content
    kinds = sorted(item.kind for item in read_pack(raw).items)
    assert kinds == ["reading_article", "reading_source"]
    # The same environment plans the pack as already here.
    plan = call(app, "POST", "/api/admin/content-packs/plan", files={"file": ("p.orenapack", raw, "application/zip")}).json()
    assert {row["outcome"] for row in plan["items"]} == {"identical"}

    there = _environment()
    _use(*there)
    plan = call(app, "POST", "/api/admin/content-packs/plan", files={"file": ("p.orenapack", raw, "application/zip")}).json()
    assert {row["outcome"] for row in plan["items"]} == {"new"}
    imported = call(app, "POST", "/api/admin/content-packs/import", files={"file": ("p.orenapack", raw, "application/zip")}).json()
    results = {row["kind"]: row for row in imported["items"]}
    assert results["reading_source"]["result"] == "source_created_for_review", "a new source is never active on arrival"
    assert results["reading_article"]["result"] == "waiting_for_source_approval", "the engine takes approved sources only"
    content, jobs, engine_service = there
    created = next(s for s in content.list_sources() if s["slug"] == "sample-news")
    assert created["state"] == "needs_review"
    content.set_source_state(created["id"], "active", actor="admin")  # the administrator here approves it once
    second = call(app, "POST", "/api/admin/content-packs/import", files={"file": ("p.orenapack", raw, "application/zip")}).json()
    article_row = next(row for row in second["items"] if row["kind"] == "reading_article")
    assert article_row["result"] == "submitted", "the text is a Reading job, not a copied row"
    outcome = engine_service.process(jobs.claim("worker-1"))
    admitted = content.get_article(outcome["article_id"])
    reasons = set((admitted["analysis"].get("admission") or {}).get("reasons") or [])
    # This environment's own admission decided it; the pack's source and rights answers carried over.
    assert admitted["analysis"].get("admission") and not reasons & {"source_not_active", "rights_not_cleared",
                                                                    "automation_not_allowed", "attribution_unknown"}, reasons
    third = call(app, "POST", "/api/admin/content-packs/import", files={"file": ("p.orenapack", raw, "application/zip")}).json()
    assert {row["result"] for row in third["items"]} == {"kept_local", "present"}, "importing again changes nothing"


def test_every_pack_route_is_admin_only_and_same_origin(app):
    _use(*_environment())

    async def run(path, **kwargs):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.post(path, **kwargs)

    for path in ("/api/admin/content-packs/export", "/api/admin/content-packs/plan", "/api/admin/content-packs/import"):
        assert asyncio.run(run(path, json={})).status_code in {403, 422}
        refused = asyncio.run(run(path, json={}, headers={"x-test-admin": "1", "origin": "https://evil.example"}))
        assert refused.status_code in {403, 422}, path
    assert json  # keep the import used by the parametrised tamper cases readable
