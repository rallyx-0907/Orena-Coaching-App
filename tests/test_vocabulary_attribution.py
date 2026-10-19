"""CC-CEDICT attribution on a collection's own record: dry run, apply, idempotence, preservation."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy.orm import Session

from tests.test_content_lifecycle_reversible import _collection
from writing_coach import vocabulary_attribution as va
from writing_coach.licences import DATASETS
from writing_coach.persistence.models import VocabularyCollection
from writing_coach.persistence.vocabulary_repository import sqlite_vocabulary_repository

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "apply_vocab_attribution.py"


def _repo(tmp_path):
    repo = sqlite_vocabulary_repository(tmp_path / "v.db")
    repo.initialize()
    for cid, sources in (("zh-a", ["CC-CEDICT (pinyin)"]), ("zh-b", ["CC-CEDICT"]), ("en-a", ["CMUdict"])):
        _collection(repo, cid)
        with Session(repo.engine) as session, session.begin():
            session.get(VocabularyCollection, cid).provenance = {"data_sources": sources, "keep": 1}
    return repo


def _prov(repo, cid):
    with Session(repo.engine) as session:
        return dict(session.get(VocabularyCollection, cid).provenance)


def test_the_statement_comes_from_the_registry_and_names_licence_and_source() -> None:
    lic = va.cedict_licence()
    dataset = next(d for d in DATASETS if d.id == "cc-cedict")
    assert lic["attribution"] == dataset.attribution and "Paul Andrew Denisowski" in lic["statement"]
    assert "CC BY-SA 4.0" in lic["statement"] and "CC-CEDICT" in lic["statement"]


def test_dry_run_selects_only_cedict_collections_and_writes_nothing(tmp_path) -> None:
    repo = _repo(tmp_path)
    assert [r["id"] for r in va.plan(repo.engine)] == ["zh-a", "zh-b"]
    assert "licence" not in _prov(repo, "zh-a")


def test_apply_is_idempotent_and_preserves_other_keys(tmp_path) -> None:
    repo = _repo(tmp_path)
    assert [r["change"] for r in va.apply(repo.engine)] == [True, True]
    assert _prov(repo, "zh-a")["licence"] == va.cedict_licence() and _prov(repo, "zh-a")["keep"] == 1
    assert "licence" not in _prov(repo, "en-a")
    assert [r["change"] for r in va.apply(repo.engine)] == [False, False]
    assert [r["id"] for r in va.apply(repo.engine, ["en-a"])] == ["en-a"]


def test_cli_dry_run_then_apply(tmp_path, capsys) -> None:
    repo = _repo(tmp_path)
    spec = importlib.util.spec_from_file_location("apply_vocab_attribution", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    url = f"sqlite:///{tmp_path / 'v.db'}"
    assert module.main(["--url", url]) == 0 and "dry run" in capsys.readouterr().out
    assert "licence" not in _prov(repo, "zh-a")
    assert module.main(["--url", url, "--apply"]) == 0
    assert _prov(repo, "zh-a")["licence"]["licence"] == "CC BY-SA 4.0"
