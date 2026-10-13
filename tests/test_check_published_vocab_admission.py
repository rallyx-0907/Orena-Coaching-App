"""The read-only checker for published vocabulary collections without a valid admission."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from tests.test_content_lifecycle_reversible import _collection
from writing_coach.persistence.models import VocabularyCollection
from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

GOOD = {
    "rights_status": "licensed", "completeness": "complete", "review_status": "approved",
    "publication_attested": True, "attested_by": "admin@example.com",
}
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_published_vocab_admission.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_published_vocab_admission", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def database(tmp_path):
    path = tmp_path / "vocabulary.db"
    repo = sqlite_vocabulary_repository(path)
    repo.initialize()
    _collection(repo, "good")
    repo.finalize_collection_publication("good", admission=GOOD)
    _collection(repo, "pending")
    # Rows published through the old route: status set, admission missing or partial.
    for cid, admission in (("legacy-none", None), ("legacy-partial", {**GOOD, "completeness": "partial", "attested_by": ""})):
        _collection(repo, cid)
        with Session(repo.engine) as session, session.begin():
            row = session.get(VocabularyCollection, cid)
            row.catalog_status = "published"
            row.provenance = {"publisher": "test", **({"admission": admission} if admission else {})}
    return repo, f"sqlite:///{path}"


def _snapshot(repo):
    with Session(repo.engine) as session:
        return sorted(
            (r.id, r.catalog_status, repr(r.provenance), r.updated_at)
            for r in session.query(VocabularyCollection).all()
        )


def test_lists_exactly_the_published_collections_that_fail_admission(database):
    repo, _ = database
    found = {item["id"]: item for item in _load().find_unadmitted_published(repo.engine)}
    assert set(found) == {"legacy-none", "legacy-partial"}
    assert found["legacy-none"]["reason"] == "no admission record"
    assert "completeness is not complete" in found["legacy-partial"]["reason"]
    assert "attested_by is empty" in found["legacy-partial"]["reason"]
    assert found["legacy-none"]["language_code"] == "en" and found["legacy-none"]["entries"] == 1


def test_writes_nothing(database):
    repo, _ = database
    before = _snapshot(repo)
    _load().find_unadmitted_published(repo.engine)
    assert _snapshot(repo) == before


def test_cli_reports_and_never_prints_the_url(database, capsys, monkeypatch):
    _, url = database
    monkeypatch.setenv("POSTGRES_RUNTIME_URL", url)
    assert _load().main([]) == 1
    out = capsys.readouterr().out
    assert "legacy-none" in out and "legacy-partial" in out
    assert "- good " not in out and "- pending " not in out
    assert url not in out and "sqlite" not in out


def test_cli_is_clean_when_every_published_collection_is_admitted(tmp_path, capsys, monkeypatch):
    path = tmp_path / "clean.db"
    repo = sqlite_vocabulary_repository(path)
    repo.initialize()
    _collection(repo, "good")
    repo.finalize_collection_publication("good", admission=GOOD)
    monkeypatch.setenv("POSTGRES_RUNTIME_URL", f"sqlite:///{path}")
    assert _load().main([]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_refuses_without_a_database(capsys, monkeypatch):
    monkeypatch.delenv("POSTGRES_RUNTIME_URL", raising=False)
    assert _load().main([]) == 2
    assert "refused" in capsys.readouterr().out
