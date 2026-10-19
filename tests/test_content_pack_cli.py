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


# The tables a content pack may write: Reading's content, its admission and review records. An explicit list, not a
# name prefix - `reading_attempts`, `reading_ability_projections` and the legacy sessions are learner tables.
CONTENT_TABLES = frozenset({
    "reading_sources", "reading_source_items", "reading_articles", "reading_article_targets", "reading_derived_texts",
    "reading_ingestion_jobs", "reading_review_events", "reading_comprehension_sets", "reading_comprehension_questions",
})
LEARNER_TABLES = frozenset({"reading_attempts", "reading_ability_projections", "reading_legacy_attempts",
                            "reading_legacy_sessions"})


def test_the_content_table_allowlist_names_no_learner_table():
    from writing_coach.persistence.models import Base

    names = {t.name for t in Base.metadata.sorted_tables}
    assert CONTENT_TABLES <= names and LEARNER_TABLES <= names
    assert not CONTENT_TABLES & LEARNER_TABLES


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
    planned = {r["kind"]: r["status"] for r in plan["items"]}
    assert code == 0 and plan["dry_run"] is True, plan
    assert planned == {"reading_source": "new", "reading_article": "held", "vocabulary_collection": "new"}, (
        "the plan predicts what the import does: the source arrives unapproved, so its article is held")
    assert _counts(target) == before and not store and not events, "a dry run writes nothing"

    code, applied = _run(cli, capsys, "import", "--pack", str(pack_file), "--apply", "--actor", "tester", "--log", str(log))
    assert code == 0, applied
    by_kind = {r["kind"]: r for r in applied["items"]}
    assert by_kind["reading_source"]["status"] == "new" and "unapproved" in by_kind["reading_source"]["reason"]
    assert by_kind["reading_article"]["status"] == "held", "no article is admitted before its source is approved here"
    assert set(store) == {"sample-words", "qa-words"}
    after = _counts(target)
    changed = {name for name in after if after[name] != before[name]}
    assert changed and changed <= CONTENT_TABLES, changed - CONTENT_TABLES
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


def test_articles_of_a_source_already_here_and_unchanged_import_without_a_key_error(cli, capsys, tmp_path):
    """Production, 2026-10-19: every article of a source the target already held unchanged was refused "KeyError".

    The article was present here, so the import finished it - and the typographic cover it makes for a present article
    without a thumbnail read the title from the dedupe lookup, which carried only the id and the status."""

    from writing_coach.book_asset_store import FilesystemBookAssetStore

    here = _environment()
    content, jobs, engine_service = here
    article_id = _published_sample(*here)
    admin_api.configure_reading_admin(admin_guard=None, content=content, jobs=jobs, engine=engine_service,
                                      audit=lambda *a, **k: None,
                                      asset_store=FilesystemBookAssetStore(tmp_path / "assets"))  # fmt: skip
    _vocabulary({})
    pack_file, log = tmp_path / "x.orenapack", tmp_path / "log.jsonl"
    assert _run(cli, capsys, "export", "--kinds", "reading", "--out", str(pack_file), "--log", str(log))[0] == 0
    assert not content.has_thumbnail(article_id), "the case: a present article without a thumbnail"

    code, plan = _run(cli, capsys, "import", "--pack", str(pack_file), "--log", str(log))
    assert code == 0 and {r["status"] for r in plan["items"]} == {"unchanged"}, plan
    before = _counts(here)
    code, applied = _run(cli, capsys, "import", "--pack", str(pack_file), "--apply", "--log", str(log))
    rows = {r["kind"]: r for r in applied["items"]}
    assert code == 0, applied
    assert rows["reading_source"]["status"] == "unchanged"
    assert rows["reading_article"]["status"] == "new" and "thumbnail" in rows["reading_article"]["reason"], rows
    assert content.has_thumbnail(article_id), "the present article now has its typographic cover"
    after = _counts(here)
    assert {name for name in after if after[name] != before[name]} <= CONTENT_TABLES
    code, again = _run(cli, capsys, "import", "--pack", str(pack_file), "--apply", "--log", str(log))
    assert code == 0 and {r["status"] for r in again["items"]} == {"unchanged"}, "a re-run changes nothing"


def test_an_item_failure_names_what_was_missing_never_a_bare_exception_name():
    assert content_pack_api.failure_reason(KeyError("title")) == "internal_error: missing key 'title' (KeyError)"
    assert content_pack_api.failure_reason(ValueError("bad language")) == "internal_error: ValueError: bad language"

    class Coded(Exception):
        code = "reading_source_not_active"

    assert content_pack_api.failure_reason(Coded("x")) == "reading_source_not_active"

    class DriverError(Exception):
        pass

    # A driver's message may carry a connection string: only the type is reported (the trace goes to the log).
    assert content_pack_api.failure_reason(DriverError("postgresql://u:secret@h/db")) == "internal_error: DriverError"


def test_a_failed_import_item_reports_its_reason_through_the_cli(cli, capsys, tmp_path, monkeypatch):
    here = _environment()
    _use(*here)
    _published_sample(*here)
    pack_file = tmp_path / "x.orenapack"
    assert _run(cli, capsys, "export", "--kinds", "reading", "--out", str(pack_file), "--log", str(tmp_path / "l"))[0] == 0

    def broken(item, admin, **kwargs):
        raise KeyError("license_note")

    monkeypatch.setattr(admin_api, "pack_import_reading", broken)
    code, applied = _run(cli, capsys, "import", "--pack", str(pack_file), "--apply", "--log", str(tmp_path / "l"))
    reasons = {r["reason"] for r in applied["items"]}
    assert code == 1 and "internal_error: missing key 'license_note' (KeyError)" in reasons, reasons
    assert "KeyError" not in reasons


def test_a_log_that_cannot_be_written_never_loses_the_committed_import(cli, capsys, tmp_path):
    here = _environment()
    _use(*here)
    _published_sample(*here)
    pack_file = tmp_path / "x.orenapack"
    assert _run(cli, capsys, "export", "--kinds", "reading", "--out", str(pack_file), "--log", str(tmp_path / "l"))[0] == 0
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("a file where the log's directory would be", encoding="utf-8")
    code = cli.main(["import", "--pack", str(pack_file), "--apply", "--log", str(blocker / "log.jsonl")],
                    bootstrap=lambda: None)  # fmt: skip
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert code == cli.LOG_NOT_WRITTEN and report["log"] is None and report["summary"], report
    assert "Log not written" in captured.err and '"command": "import"' in captured.err, "the record is printed instead"


def test_the_default_log_is_outside_the_repository(cli, tmp_path):
    root = cli.ROOT.resolve()
    assert cli.default_log_path({"CONTENT_PACK_LOG": str(tmp_path / "x.jsonl")}) == tmp_path / "x.jsonl"
    assert cli.default_log_path({"WRITING_DB": str(tmp_path / "data" / "writing.db")}) == (
        (tmp_path / "data").resolve() / cli.LOG_NAME)
    for environ in ({}, {"WRITING_DB": str(root / "data" / "writing.db")}):
        assert not cli.default_log_path(environ).resolve().is_relative_to(root), environ


def test_the_cli_reads_a_pack_within_the_routes_limits(cli, capsys, tmp_path, monkeypatch):
    from writing_coach import content_packs

    assert cli.MAX_PACK_BYTES == content_packs.MAX_PACK_BYTES, "the CLI accepts exactly what the route accepts"
    pack_file = tmp_path / "big.orenapack"
    pack_file.write_bytes(build_pack([PackItem(kind="vocabulary_collection", natural_key="c", data=dict(COLLECTION))],
                                     created_by="t", environment="t", app_version="t", filters={}))  # fmt: skip
    monkeypatch.setattr(cli, "MAX_PACK_BYTES", pack_file.stat().st_size - 1)
    assert cli.main(["import", "--pack", str(pack_file)], bootstrap=lambda: None) == 2
    assert "pack_too_large" in capsys.readouterr().err
