"""Dataset attribution on a collection's own record: mapping, dry run, apply, idempotence, preservation."""

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
    rows = (
        ("zh-a", ["CC-CEDICT (pinyin)"]),
        ("zh-b", ["CC-CEDICT"]),
        ("en-a", ["CMUdict", "CEFR-J Vocabulary Profile 1.5"]),
        ("plain", ["hand-written"]),
    )
    for cid, sources in rows:
        _collection(repo, cid)
        with Session(repo.engine) as session, session.begin():
            session.get(VocabularyCollection, cid).provenance = {"data_sources": sources, "keep": 1}
    return repo


def _prov(repo, cid):
    with Session(repo.engine) as session:
        return dict(session.get(VocabularyCollection, cid).provenance)


def _dataset(dataset_id):
    return next(d for d in DATASETS if d.id == dataset_id)


def test_the_statement_comes_from_the_registry_and_names_licence_and_source() -> None:
    lic = va.cedict_licence()
    assert lic["attribution"] == _dataset("cc-cedict").attribution and "Paul Andrew Denisowski" in lic["statement"]
    assert "CC BY-SA 4.0" in lic["statement"] and "CC-CEDICT" in lic["statement"]
    assert "shared under CC BY-SA 4.0" in lic["statement"]


def test_cefrj_and_cmudict_notices_use_the_registry_wording() -> None:
    cefrj, cmu = va.licence_object("cefrj-vocabulary"), va.licence_object("cmudict")
    assert _dataset("cefrj-vocabulary").attribution in cefrj["statement"] and "Yukio Tono" in cefrj["statement"]
    assert "shared under" not in cefrj["statement"]
    assert "Copyright (C) 1993-2015 Carnegie Mellon University" in cmu["statement"]
    assert cmu["licence"] == _dataset("cmudict").licence and cmu["licence_url"].startswith("https://")


def test_data_sources_map_to_registry_ids_in_registry_order() -> None:
    assert va.matched_datasets({"data_sources": ["CMUdict", "cefr-j wordlist", "CC-CEDICT"]}) == [
        "cc-cedict", "cefrj-vocabulary", "cmudict"]
    assert va.matched_datasets({"data_sources": ["CEFRJ"]}) == ["cefrj-vocabulary"]
    assert va.matched_datasets({"data_sources": ["hand-written"]}) == []
    assert va.matched_datasets({}) == [] and va.matched_datasets(None) == []


def test_dry_run_selects_only_collections_naming_a_known_dataset_and_writes_nothing(tmp_path) -> None:
    repo = _repo(tmp_path)
    assert [r["id"] for r in va.plan(repo.engine)] == ["en-a", "zh-a", "zh-b"]
    assert "licences" not in _prov(repo, "zh-a")


def test_apply_writes_a_list_is_idempotent_and_preserves_other_keys(tmp_path) -> None:
    repo = _repo(tmp_path)
    assert [r["change"] for r in va.apply(repo.engine)] == [True, True, True]
    assert _prov(repo, "zh-a")["licences"] == [va.cedict_licence()] and _prov(repo, "zh-a")["keep"] == 1
    assert [item["id"] for item in _prov(repo, "en-a")["licences"]] == ["cefrj-vocabulary", "cmudict"]
    assert "licences" not in _prov(repo, "plain")
    assert [r["change"] for r in va.apply(repo.engine)] == [False, False, False]


def test_the_old_single_licence_key_is_removed_and_the_rerun_converges(tmp_path) -> None:
    repo = _repo(tmp_path)
    with Session(repo.engine) as session, session.begin():
        row = session.get(VocabularyCollection, "zh-a")
        row.provenance = {**row.provenance, "licence": va.cedict_licence(), "licences": [va.cedict_licence()]}
    assert {r["id"]: r["change"] for r in va.plan(repo.engine)}["zh-a"] is True
    va.apply(repo.engine)
    assert "licence" not in _prov(repo, "zh-a") and _prov(repo, "zh-a")["licences"] == [va.cedict_licence()]
    assert _prov(repo, "zh-a")["keep"] == 1
    assert [r["change"] for r in va.apply(repo.engine)] == [False, False, False]


def test_explicit_id_without_a_matching_source_is_refused_with_a_warning(tmp_path) -> None:
    repo = _repo(tmp_path)
    rows = va.apply(repo.engine, ["plain", "nope", "zh-b"])
    by_id = {r["id"]: r for r in rows}
    assert by_id["plain"]["change"] is False and "no matching data source" in by_id["plain"]["warning"]
    assert by_id["nope"]["warning"] == "collection not found"
    assert by_id["zh-b"]["change"] is True
    assert "licences" not in _prov(repo, "plain") and "licences" in _prov(repo, "zh-b")


def test_cli_dry_run_then_apply(tmp_path, capsys) -> None:
    repo = _repo(tmp_path)
    spec = importlib.util.spec_from_file_location("apply_vocab_attribution", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    url = f"sqlite:///{tmp_path / 'v.db'}"
    assert module.main(["--url", url]) == 0 and "dry run" in capsys.readouterr().out
    assert "licences" not in _prov(repo, "zh-a")
    assert module.main(["--url", url, "--id", "plain"]) == 0 and "WARNING" in capsys.readouterr().out
    assert module.main(["--url", url, "--apply"]) == 0
    assert _prov(repo, "zh-a")["licences"][0]["licence"] == "CC BY-SA 4.0"
