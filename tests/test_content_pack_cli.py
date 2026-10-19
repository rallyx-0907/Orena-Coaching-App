"""scripts/content_pack.py: Reading and vocabulary moved between two environments by the shared Admin implementation."""

from __future__ import annotations

import importlib.util
import json

import pytest

from tests.test_content_packs import _environment, _published_sample, _use
from writing_coach import content_pack_api
from writing_coach import reading_admin_api as admin_api
from writing_coach.content_packs import PackItem, build_pack, read_pack


def _load():
    spec = importlib.util.spec_from_file_location("content_pack_cli", "scripts/content_pack.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


@pytest.fixture()
def cli():
    yield _load()
    admin_api.configure_reading_admin(admin_guard=None)
    content_pack_api.configure_content_packs()


def _audited(environment):
    events: list[tuple] = []
    content, jobs, engine_service = environment
    admin_api.configure_reading_admin(admin_guard=None, content=content, jobs=jobs, engine=engine_service,
                                      audit=lambda action, **kw: events.append((action, kw)))
    return events


def _vocabulary(store):
    """Stands in for the application's vocabulary repository: a dict of collections."""

    content_pack_api.configure_content_packs(
        vocabulary_ids=lambda languages, prefix: [k for k in store if k.startswith(prefix)],
        vocabulary_export=lambda cid: store.get(cid),
        vocabulary_import=lambda data, **kw: store.setdefault(data["id"], dict(data)) and {"collection_id": data["id"],
                                                                                         "status": "published", "imported": len(data["entries"])})  # fmt: skip


COLLECTION = {"id": "sample-words", "title": "Sample", "language_code": "en", "entries": [{"identity_key": "a|1"}]}


def _run(cli, capsys, *argv):
    code = cli.main(list(argv), bootstrap=lambda: None)
    out = capsys.readouterr().out
    return code, (json.loads(out) if out.strip().startswith("{") else out)


def _counts(environment):
    from sqlalchemy import text

    from writing_coach.persistence.models import Base

    engine = environment[0]._engine if hasattr(environment[0], "_engine") else environment[0].engine
    with engine.connect() as connection:
        return {t.name: connection.execute(text(f'SELECT COUNT(*) FROM "{t.name}"')).scalar() for t in Base.metadata.sorted_tables}


def test_round_trip_dry_run_apply_and_reapply_is_idempotent_and_touches_no_learner_table(cli, capsys, tmp_path):
    source = _environment()
    _use(*source)
    _published_sample(*source)
    _vocabulary({"sample-words": COLLECTION, "qa-words": {**COLLECTION, "id": "qa-words"}})
    pack_file = tmp_path / "x.orenapack"
    log = tmp_path / "log.jsonl"
    code, dry = _run(cli, capsys, "export", "--kinds", "reading,vocabulary", "--dry-run", "--log", str(log))
    assert code == 0 and dry["dry_run"] is True and not pack_file.exists() and dry["counts"]["reading_article"] == 1
    code, report = _run(cli, capsys, "export", "--kinds", "reading,vocabulary", "--out", str(pack_file), "--log", str(log),
                        "--actor", "tester", "--exclude-source-prefix", "nothing-")
    assert code == 0 and report["pack"] == str(pack_file)
    kinds = sorted(item.kind for item in read_pack(pack_file.read_bytes()).items)
    assert kinds == ["reading_article", "reading_source", "vocabulary_collection", "vocabulary_collection"]
    code, _ = _run(cli, capsys, "export", "--kinds", "reading,vocabulary", "--out", str(tmp_path / "y.orenapack"),
                   "--exclude-source-prefix", "sample-", "--collection-prefix", "zzz-")
    assert code == 1, "everything excluded: nothing to export"

    target = _environment()
    _use(*target)
    events = _audited(target)
    store: dict = {}
    _vocabulary(store)
    before = _counts(target)
    code, plan = _run(cli, capsys, "import", "--pack", str(pack_file), "--log", str(log))
    assert code == 0 and plan["dry_run"] is True and {r["status"] for r in plan["items"]} == {"new"}
    assert _counts(target) == before and not store and not events, "a dry run writes nothing"

    code, applied = _run(cli, capsys, "import", "--pack", str(pack_file), "--apply", "--actor", "tester", "--log", str(log))
    assert code == 0, applied
    by_kind = {r["kind"]: r for r in applied["items"]}
    assert by_kind["reading_source"]["status"] == "new" and "unapproved" in by_kind["reading_source"]["reason"]
    assert by_kind["reading_article"]["status"] == "held", "no article is admitted before its source is approved here"
    assert set(store) == {"sample-words", "qa-words"}
    after = _counts(target)
    changed = {name for name in after if after[name] != before[name]}
    assert changed and all(name.startswith("reading_") for name in changed), changed
    assert [e for e in events if e[0] == "admin.content_pack_import"][0][1]["actor_key"] == "cli:tester"
    created = next(s for s in target[0].list_sources() if s["slug"] == "sample-news")
    assert created["state"] == "needs_review"

    code, again = _run(cli, capsys, "import", "--pack", str(pack_file), "--apply", "--log", str(log))
    assert code == 0 and {r["status"] for r in again["items"] if r["kind"] != "reading_article"} == {"unchanged"}
    _run(cli, capsys, "import", "--pack", str(pack_file), "--log", str(log))
    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [line["command"] for line in lines].count("import") == 2 and lines[0]["command"] == "export"


def test_a_refused_item_and_a_conflict_exit_non_zero(cli, capsys, tmp_path):
    here = _environment()
    _use(*here)
    _vocabulary({})
    orphan = PackItem(kind="reading_article", natural_key="ghost:abc", data={
        "source_slug": "ghost", "body": "Some text of an article.", "title": "T", "language": "en", "comprehension_sets": []})
    pack_file = tmp_path / "o.orenapack"
    pack_file.write_bytes(build_pack([orphan], created_by="t", environment="t", app_version="t", filters={}))
    code, plan = _run(cli, capsys, "import", "--pack", str(pack_file), "--log", str(tmp_path / "l.jsonl"))
    assert code == 1 and plan["items"][0]["status"] == "refused" and "pack_source_missing" in plan["items"][0]["reason"]
    code, applied = _run(cli, capsys, "import", "--pack", str(pack_file), "--apply", "--log", str(tmp_path / "l.jsonl"))
    assert code == 1 and applied["items"][0]["status"] == "refused"
    junk = tmp_path / "junk.orenapack"
    junk.write_bytes(b"not a zip")
    assert cli.main(["import", "--pack", str(junk)], bootstrap=lambda: None) == 2
