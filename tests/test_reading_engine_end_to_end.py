"""One submission, from the admin's HTTP request to what a learner reads.

Every other test in this engine proves one seam. This one crosses all of them
in the order a real import does: an administrator posts a file to the admin
route, the request returns a job and nothing else, a worker in a *separate*
step picks that job up, reads the upload back from the asset store, produces a
candidate, an administrator reviews and publishes it, and only then does the
learner route answer with the text.

The upload is the part this file exists for. The bytes an admin posts are not
in the job row - a row is not a place to keep a file - so they must be stored
durably at submission and read back by whatever process claims the job later,
which is not the process that accepted it. Before this was wired, a file job
survived its own request and then failed in the worker with the file it had
never been given.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool

from writing_coach import reading_admin_api as admin_api
from writing_coach import reading_articles_api as learner_api
from writing_coach.book_asset_store import FilesystemBookAssetStore
from writing_coach.persistence.models import Base
from writing_coach.persistence.reading_content_repository import ReadingContentRepository
from writing_coach.persistence.reading_job_repository import ReadingJobRepository
from writing_coach.reading_content_engine import ReadingContentEngine
from writing_coach.reading_worker import ReadingWorker

ADMIN = {"google_sub": "sub-admin", "email": "admin@example.com", "role": "admin"}
FILE_TEXT = (
    "<h1>The market on Saturday</h1>"
    "<p>The market opened early on Saturday and the square filled before the sun was high. "
    "Farmers arrived with boxes of fruit, and children ran between the stalls while their "
    "parents argued about prices.</p>"
    "<p>By noon the best tomatoes were gone and the bakery had sold every loaf. The oldest "
    "seller said the crowd was the largest she had seen this year, and the council has "
    "promised a permanent roof before the winter markets begin.</p>"
)


def guard(request):
    if request.headers.get("x-test-admin") != "1":
        raise HTTPException(403, "Platform administrator access required")
    return ADMIN


@pytest.fixture()
def world(tmp_path):
    database = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(database, "connect")
    def _foreign_keys(dbapi_connection, record):  # noqa: ANN001
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(database)
    content = ReadingContentRepository(database)
    content.ensure_built_in_sources()
    jobs = ReadingJobRepository(database)
    assets = FilesystemBookAssetStore(tmp_path / "uploads")
    engine = ReadingContentEngine(content=content, jobs=jobs, asset_store=assets)
    admin_api.configure_reading_admin(
        admin_guard=guard, content=content, jobs=jobs, engine=engine, audit=None
    )
    learner_api.configure_reading_articles(content, language_supported=lambda code: code in {"en", "zh"})
    admin_app, learner_app = FastAPI(), FastAPI()
    admin_app.include_router(admin_api.router)
    learner_app.include_router(learner_api.router)
    # The worker is a different process in a deployment; here it is at least a
    # different object, holding no state from the request that queued the work.
    worker = ReadingWorker(engine=engine, jobs=jobs, worker_id="worker-1", asset_reader=assets.get)
    yield {
        "admin": admin_app, "learner": learner_app, "content": content, "jobs": jobs,
        "worker": worker, "assets": assets, "engine": engine,
    }
    admin_api.configure_reading_admin(admin_guard=None)
    learner_api.configure_reading_articles(None)


def call(app, method, path, *, admin=True, **kwargs):
    headers = {"x-test-admin": "1"} if admin else {}
    if method.upper() != "GET":
        headers["origin"] = "http://testserver"

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, headers=headers, **kwargs)

    return asyncio.run(run())


def _post_file(world, *, name="market.html", body=FILE_TEXT.encode("utf-8")):
    return call(
        world["admin"],
        "POST",
        "/api/admin/reading/jobs",
        data={"kind": "file", "title": "The market on Saturday", "language": "en",
              "can_republish": "true"},
        files={"upload": (name, body, "text/html")},
    )


def test_an_uploaded_file_travels_from_the_request_to_the_learner(world):
    submitted = _post_file(world)
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]

    # The request did the work of accepting, and no more.
    queued = call(world["admin"], "GET", f"/api/admin/reading/jobs/{job_id}").json()
    assert queued["status"] == "queued" and queued["stage"] == "queued"
    assert call(world["admin"], "GET", "/api/admin/reading/queue").json()["items"] == []

    # A worker that never saw the request picks it up and finds the file.
    outcome = world["worker"].run_once()
    assert outcome["result_kind"] == "article_created", outcome
    article_id = outcome["article_id"]

    article = call(world["admin"], "GET", f"/api/admin/reading/articles/{article_id}").json()
    assert "The market opened early" in article["body"]
    assert "<p>" not in article["body"], "markup never survives into what a learner reads"
    assert article["status"] == "needs_review"

    published = call(world["admin"], "POST", f"/api/admin/reading/articles/{article_id}/status",
                     json={"status": "published"})
    assert published.status_code == 200

    listed = call(world["learner"], "GET", "/api/reading/articles?language=en", admin=False).json()
    assert [item["id"] for item in listed["items"]] == [article_id]
    read = call(world["learner"], "GET", f"/api/reading/articles/{article_id}", admin=False).json()
    assert "The market opened early" in read["body"]


def test_the_upload_is_stored_under_a_key_the_job_carries(world):
    job_id = _post_file(world).json()["id"]
    job = world["jobs"].get_job(job_id)
    assert job["input_asset_key"], "a file job must name where its bytes went"
    assert world["assets"].exists(job["input_asset_key"])
    assert b"The market opened early" in world["assets"].get(job["input_asset_key"])
    # The bytes are not in the row: a job row is metadata, never a file.
    assert "payload" not in job["input_json"]
    assert len(str(job["input_json"])) < 2000


def test_a_worker_with_no_file_fails_the_job_rather_than_inventing_one(world):
    """The upload is gone - a wiped volume, a store that lost it. The job must
    say so and stop, not produce an article from an empty document."""
    job_id = _post_file(world).json()["id"]
    world["assets"].delete(world["jobs"].get_job(job_id)["input_asset_key"])
    outcome = world["worker"].run_once()
    assert outcome["result_kind"] == "failed"
    assert world["jobs"].get_job(job_id)["last_error_code"] in {"empty_source", "upload_missing"}


def test_the_upload_is_released_once_its_text_is_safely_stored(world):
    """The snapshot holds the text after a successful import, so the uploaded
    file has no second reader and is not kept forever."""
    job_id = _post_file(world).json()["id"]
    key = world["jobs"].get_job(job_id)["input_asset_key"]
    world["worker"].run_once()
    assert not world["assets"].exists(key)


def test_a_failed_file_job_keeps_its_upload_so_retry_has_something_to_read(world):
    # An allowed extension whose bytes are not text: refused by the adapter,
    # which is a failure the admin can act on by uploading the right file.
    submitted = _post_file(world, name="broken.html", body=b"%PDF-1.7 not text at all")
    job_id = submitted.json()["id"]
    key = world["jobs"].get_job(job_id)["input_asset_key"]
    outcome = world["worker"].run_once()
    assert outcome["result_kind"] == "failed"
    assert world["assets"].exists(key), "a retry needs the same bytes"
    retried = call(world["admin"], "POST", f"/api/admin/reading/jobs/{job_id}/retry")
    assert retried.status_code == 202
    assert world["jobs"].get_job(retried.json()["id"])["input_asset_key"] == key


def test_two_uploads_of_the_same_file_are_one_job_and_one_stored_copy(world):
    first = _post_file(world).json()
    second = _post_file(world).json()
    assert second["duplicate"] is True and second["id"] == first["id"]
    stored = world["jobs"].get_job(first["id"])["input_asset_key"]
    assert world["assets"].exists(stored)


def test_a_pasted_text_needs_no_asset_at_all(world):
    response = call(world["admin"], "POST", "/api/admin/reading/jobs",
                    data={"kind": "text", "text": FILE_TEXT, "language": "en"})
    job = world["jobs"].get_job(response.json()["id"])
    assert job["input_asset_key"] == ""
    assert world["worker"].run_once()["result_kind"] == "article_created"
