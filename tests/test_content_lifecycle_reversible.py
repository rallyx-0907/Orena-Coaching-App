"""Nothing in the editorial flow is a one-way door.

Media already had the whole lifecycle. A book could only be archived - the one
recovery path an operator has for a wrong import was irreversible, which makes
it a path nobody dares use. A vocabulary collection could only be published:
there was no way to take one back at all, so the only "unpublish" available was
deleting rows.

These hold the two rules that make the states safe to press:

* every transition has a way back, and
* nothing an operator presses destroys content, provenance or history.

The vocabulary flow is the one the human settled:

    pending_review -> published <-> unpublished -> archived
    archived -> unpublished        (never straight back to learners)
"""
from __future__ import annotations

import pytest

sqlalchemy = pytest.importorskip("sqlalchemy")

from writing_coach.persistence.vocabulary_repository import (  # noqa: E402
    sqlite_vocabulary_repository,
)
from writing_coach.vocabulary_source_import import (  # noqa: E402
    detect_vocabulary_mapping,
    normalize_vocabulary_rows,
    parse_vocabulary_source,
)


def _collection(repository, collection_id="pack", status="pending_review"):
    csv = "word,meaning" + chr(10) + "allocate,phan bo" + chr(10)
    parsed = parse_vocabulary_source("pack.csv", csv.encode("utf-8"))
    detected = detect_vocabulary_mapping(parsed)
    normalized = normalize_vocabulary_rows(
        parsed, mapping=detected.mapping, language_code="en", meaning_language="vi",
        collection_framework="TOEIC", collection_level="B1",
    )
    repository.import_source(
        collection={
            "id": collection_id,
            "title": "A pack",
            "language_code": "en",
            "framework": "TOEIC",
            "level": "B1",
            "catalog_status": status,
            "origin": "imported",
            "provenance": {"publisher": "test"},
        },
        source=normalized,
        records=normalized["records"],
        mapping=detected.mapping,
        imported_by="admin@example.com",
    )
    return collection_id


@pytest.fixture()
def repository(tmp_path):
    repo = sqlite_vocabulary_repository(tmp_path / "vocabulary.db")
    repo.initialize()
    return repo


# ---- vocabulary -------------------------------------------------------------

def test_a_published_collection_can_be_taken_back_and_put_out_again(repository):
    collection_id = _collection(repository)
    repository.set_collection_status(collection_id, "published", actor="admin@example.com")
    assert repository.get_collection(collection_id, status=None)["catalog_status"] == "published"

    taken = repository.set_collection_status(collection_id, "unpublished", actor="admin@example.com")
    assert taken["catalog_status"] == "unpublished"
    # The words are all still there - this is a state, not a deletion.
    assert repository.get_collection(collection_id, status=None)["entries"]

    back = repository.set_collection_status(collection_id, "published", actor="admin@example.com")
    assert back["catalog_status"] == "published"


def test_restoring_an_archived_collection_does_not_put_it_in_front_of_learners(repository):
    """The human's rule: restore returns it to the shelf, not to the learner.
    Publishing again is a separate, deliberate act."""
    collection_id = _collection(repository)
    repository.set_collection_status(collection_id, "published", actor="a@b.c")
    repository.set_collection_status(collection_id, "archived", actor="a@b.c")
    assert repository.get_collection(collection_id, status=None)["catalog_status"] == "archived"

    restored = repository.set_collection_status(collection_id, "unpublished", actor="a@b.c")
    assert restored["catalog_status"] == "unpublished"


def test_a_transition_the_flow_does_not_allow_is_refused(repository):
    collection_id = _collection(repository)
    # Straight from archived to published would put content in front of a
    # learner that nobody looked at again.
    repository.set_collection_status(collection_id, "published", actor="a@b.c")
    repository.set_collection_status(collection_id, "archived", actor="a@b.c")
    with pytest.raises(ValueError, match="archived"):
        repository.set_collection_status(collection_id, "published", actor="a@b.c")


def test_the_admission_record_survives_being_taken_back(repository):
    """Unpublishing must not erase why it was published in the first place."""
    collection_id = _collection(repository)
    repository.finalize_collection_publication(collection_id, admission={
        "rights_status": "licensed", "completeness": "complete",
        "review_status": "approved", "publication_attested": True,
        "attested_by": "admin@example.com",
    })
    repository.set_collection_status(collection_id, "unpublished", actor="admin@example.com")
    provenance = repository.get_collection(collection_id, status=None)["provenance"]
    assert provenance["admission"]["attested_by"] == "admin@example.com"
    assert provenance["admission"]["rights_status"] == "licensed"


# ---- rights advise, the administrator decides -------------------------------

def test_a_rights_answer_nobody_gave_is_a_warning_not_a_refusal():
    from writing_coach.admin_console_api import publication_warnings

    assert [w["code"] for w in publication_warnings("", "complete")] == ["rights_unknown"]
    assert publication_warnings("", "complete")[0]["level"] == "warning"


def test_a_refused_right_is_a_stronger_warning_and_still_not_a_refusal():
    from writing_coach.admin_console_api import publication_warnings

    strong = publication_warnings("not_cleared", "complete")
    assert [w["code"] for w in strong] == ["rights_not_cleared"]
    assert strong[0]["level"] == "strong"


def test_a_cleared_right_on_a_complete_collection_warns_about_nothing():
    from writing_coach.admin_console_api import publication_warnings

    assert publication_warnings("licensed", "complete") == []


def test_an_incomplete_collection_warns_without_blocking():
    from writing_coach.admin_console_api import publication_warnings

    codes = [w["code"] for w in publication_warnings("licensed", "in_progress")]
    assert codes == ["collection_incomplete"]
