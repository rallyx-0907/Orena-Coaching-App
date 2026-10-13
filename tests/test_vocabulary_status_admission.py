# ruff: noqa: F811 - fixtures are imported from the ingest-token tests, then used by name
"""F1: the collection status route must not publish around the admission gate.

`POST .../vocabulary/{id}/status` to `published` applies the same admission
function as `POST .../publish` (`_publication_admission`). Every other move
stays as it was.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

import app as app_module
from tests.test_admin_authorization_matrix import ADMIN, LEARNER
from tests.test_content_lifecycle_reversible import _collection
from tests.test_vocabulary_ingest_token import (  # noqa: F401 - fixtures
    TOKEN,
    call,
    digest,
    repository,
    secured,
)
from writing_coach import service_auth
from writing_coach.persistence.models import VocabularyCollection

@pytest.fixture
def console(secured, repository):
    """The admin console wired to the temporary vocabulary repository."""
    app_module.configure_admin_console_from_runtime()
    return secured


ORIGIN = {"origin": "http://testserver"}
GOOD = {
    "rights_status": "licensed", "completeness": "complete", "review_status": "approved",
    "publication_attested": True, "attested_by": "admin@example.com",
}


def status_url(collection_id: str) -> str:
    return f"/api/admin/console/content/vocabulary/{collection_id}/status"


def move(app, collection_id: str, status: str, **kwargs):
    return call(app, "POST", status_url(collection_id), json={"status": status}, headers=ORIGIN, **kwargs)


def state(repository, collection_id: str) -> str:
    return repository.get_collection(collection_id, status=None)["catalog_status"]


def test_session_admin_cannot_publish_a_collection_that_was_never_admitted(console, repository):
    cid = _collection(repository)
    response = move(console, cid, "published", who=ADMIN)
    assert response.status_code == 422, response.text
    assert state(repository, cid) == "pending_review"


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "rights_status": "unknown"},
        {**GOOD, "rights_status": "not_cleared"},
        {**GOOD, "completeness": "partial"},
        {**GOOD, "review_status": "pending"},
        {**GOOD, "publication_attested": False},
        {**GOOD, "attested_by": "  "},
    ],
)
def test_an_incomplete_admission_in_provenance_does_not_open_the_status_route(console, repository, bad):
    cid = _collection(repository)
    with Session(repository.engine) as session, session.begin():
        row = session.get(VocabularyCollection, cid)
        row.provenance = {**dict(row.provenance or {}), "admission": bad}
    assert move(console, cid, "published", who=ADMIN).status_code == 422
    assert state(repository, cid) == "pending_review"


def test_a_collection_admitted_through_the_publish_path_can_be_republished_by_status(console, repository):
    cid = _collection(repository)
    published = call(
        console, "POST", f"/api/admin/console/content/vocabulary/{cid}/publish", who=ADMIN, headers=ORIGIN,
        json={"rights_status": "licensed", "completeness": "complete", "attested": True},
    )
    assert published.status_code == 200, published.text
    assert state(repository, cid) == "published"
    assert move(console, cid, "unpublished", who=ADMIN).status_code == 200
    again = move(console, cid, "published", who=ADMIN)
    assert again.status_code == 200, again.text
    assert state(repository, cid) == "published"


def test_other_transitions_need_no_admission(console, repository):
    cid = _collection(repository)
    assert move(console, cid, "archived", who=ADMIN).status_code == 200
    assert move(console, cid, "unpublished", who=ADMIN).status_code == 200
    assert state(repository, cid) == "unpublished"


def test_a_learner_cannot_use_the_status_route(console, repository):
    cid = _collection(repository)
    assert move(console, cid, "published", who=LEARNER).status_code in {401, 403}
    assert state(repository, cid) == "pending_review"


def test_the_ingest_service_token_cannot_reach_the_status_route(console, repository, monkeypatch):
    monkeypatch.setenv(service_auth.ENV_NAME, digest(TOKEN))
    cid = _collection(repository)
    assert move(console, cid, "published", token=TOKEN).status_code == 401
    assert state(repository, cid) == "pending_review"


def test_the_repository_applies_the_same_gate_to_every_caller(repository):
    cid = _collection(repository)
    with pytest.raises(ValueError, match="admission"):
        repository.set_collection_status(cid, "published", actor="a@b.c")
    repository.finalize_collection_publication(cid, admission=GOOD)
    repository.set_collection_status(cid, "unpublished", actor="a@b.c")
    assert repository.set_collection_status(cid, "published", actor="a@b.c")["catalog_status"] == "published"
