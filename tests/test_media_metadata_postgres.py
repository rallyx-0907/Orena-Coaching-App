"""Media metadata in PostgreSQL (D-108.5; docs/project/proposals/MEDIA_METADATA_POSTGRES.md rev 2): the repository, the
ORM mirror of migration 20261001_0024 (still in migrations/proposed/), the one-time import and the no-wiring guarantee.

PARKED per D-109 (the migration stays in migrations/proposed/). Hermetic part (always, cheap): the ORM mirror (on its own
`MediaBase`, inert: it is NOT on `models.Base`, so no `create_all` or parity test elsewhere sees it) builds on SQLite with its
portable CHECKs, the mapping and the import's validation, and `app.py` is NOT wired to the new store. PostgreSQL part (when `ORENA_TEST_POSTGRES_URL` names a throwaway
database): the proposed revision is applied from migrations/proposed/ for the module and removed again, the ORM is compared
with the migrated schema, and the repository and the import run for real. PostgreSQL results are local execution, not CI
evidence (CI has no PostgreSQL service).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import import_media_index as importer  # noqa: E402
from writing_coach.media_library_store import MediaLibraryEntry, owner_token  # noqa: E402
from writing_coach.persistence.media_library_repository import (  # noqa: E402
    LEGACY_OWNER_TOKEN,
    MediaEntryConflict,
    MediaQuotaExceeded,
    PostgresMediaLibraryRepository,
    entry_to_row,
    lesson_parts,
)
from writing_coach.persistence.media_models import MediaBase, MediaEntry, MediaEntryPayload  # noqa: E402
from writing_coach.persistence.models import Base  # noqa: E402

PG_URL = os.getenv("ORENA_TEST_POSTGRES_URL", "")


def make_entry(i, *, library="personal", owner=None, language="en", lesson=None, provider=None, title=None, status="published"):
    token = hashlib.md5(f"t{i}".encode()).hexdigest()
    shared = library == "shared"
    provider = provider or ("youtube" if shared else "upload")
    source = {"provider": provider, "type": "admin-import" if shared else "upload", "provenance_url": "", "license": "x",
              "review_status": "y", "imported_by": "admin" if shared else "learner"}
    if owner and not shared:
        source["owner"] = owner
    return MediaLibraryEntry(
        media_id=f"{'yt' if provider == 'youtube' else 'upload'}-{token}", media_type="audio", provider=provider,
        provider_media_id=token, canonical_url="", playback={"provider": "orena", "kind": "audio", "url": f"/api/media/files/media/{token}/original.mp3"},
        title=title or f"T{i}", thumbnail={"kind": "asset", "ref": f"media/{token}/thumbnail.jpg"}, duration_ms=1000, language=language,
        level="", creator="", source=source, library=library,
        created_at=(datetime(2026, 9, 1, tzinfo=UTC) + timedelta(seconds=i)).isoformat().replace("+00:00", "Z"), lesson=lesson, status=status,
    )


REAL_LESSON = {"lesson_id": "media-lesson-1", "payload": {"asset": {"a": 1}, "transcript": {"segments": [{"text": "x"}, {"text": "y"}]}},
               "sections": ["new"], "status": "PUBLISHED", "curation": "reviewed", "language": "en"}


# --------------------------------------------------------------------------------------------- hermetic
def test_the_orm_builds_on_sqlite_with_its_portable_checks():
    engine = create_engine("sqlite://")
    MediaBase.metadata.create_all(engine)
    row = {k: v for k, v in entry_to_row(make_entry(1, owner=owner_token("a"))).items() if k not in {"payload"}}
    insert = text("INSERT INTO media_entries (" + ", ".join(row) + ") VALUES (" + ", ".join(f":{k}" for k in row) + ")")
    with engine.begin() as conn:
        conn.execute(insert, {**row, "created_at": "2026-09-01 00:00:00", "updated_at": "2026-09-01 00:00:00"})
    with pytest.raises(IntegrityError), engine.begin() as conn:  # a personal row needs an owner
        conn.execute(insert, {**row, "media_id": "upload-x", "owner_token": None, "created_at": "2026-09-01", "updated_at": "2026-09-01"})


def test_the_mirror_is_inert_it_is_not_on_the_applications_metadata():
    """The hermetic SQLite create_all (Base.metadata) must not build tables that have no migration in versions/."""
    assert "media_entries" not in Base.metadata.tables and "media_entry_payloads" not in Base.metadata.tables
    assert MediaEntry.metadata is MediaBase.metadata and MediaBase.metadata is not Base.metadata


def test_the_pg_only_checks_are_conditional_ddl():
    names = {c.name for c in MediaEntry.__table__.constraints if getattr(c, "name", None)}
    assert {"ck_media_entries_media_id", "ck_media_entries_owner_agrees", "ck_media_entries_lesson_meta"} <= names


def test_lesson_split_keeps_every_key_and_extracts_the_query_columns():
    parts = lesson_parts(make_entry(1, library="shared", lesson={**REAL_LESSON, "topic": "travel", "tags": ["a"]}))
    assert parts["meta"]["sections"] == ["new"] and "payload" not in parts["meta"]
    assert (parts["lesson_id"], parts["topic"], parts["tags"], parts["segment_count"]) == ("media-lesson-1", "travel", ["a"], 2)
    bare = lesson_parts(make_entry(2, library="shared", lesson=REAL_LESSON))
    assert bare["topic"] == "" and bare["tags"] == [] and "topic" not in bare["meta"], "topic/tags must not be invented"
    assert lesson_parts(make_entry(3, library="shared", lesson=None))["has_lesson"] is False


def test_an_unowned_personal_row_gets_the_explicit_legacy_token_and_a_shared_row_none():
    assert entry_to_row(make_entry(1, owner=None))["owner_token"] == LEGACY_OWNER_TOKEN == owner_token("legacy")
    assert entry_to_row(make_entry(2, library="shared"))["owner_token"] is None
    assert entry_to_row(make_entry(3, owner="a" * 32))["owner_token"] == "a" * 32


def _index(path: Path, entries):
    ordered = [asdict(e) for e in sorted(entries, key=lambda e: e.media_id)]
    body = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(json.dumps({"schema_version": 1, "entries": ordered, "integrity": hashlib.sha256(body.encode()).hexdigest()}), encoding="utf-8")


def test_the_import_reads_a_valid_index_and_aborts_on_every_kind_of_bad_one(tmp_path):
    good = tmp_path / "index.json"
    _index(good, [make_entry(1, owner="a" * 32), make_entry(2, library="shared", lesson=REAL_LESSON)])
    entries, fingerprint = importer.load_index(good)
    assert len(entries) == 2 and fingerprint["entries"] == 2 and len(fingerprint["sha256"]) == 64

    data = json.loads(good.read_text(encoding="utf-8"))
    data["entries"][0]["title"] = "edited after hashing"
    tampered = tmp_path / "tampered.json"
    tampered.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(importer.ImportAborted, match="integrity"):
        importer.load_index(tampered)
    (tmp_path / "junk.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(importer.ImportAborted):
        importer.load_index(tmp_path / "junk.json")
    with pytest.raises(importer.ImportAborted):
        importer.load_index(tmp_path / "missing.json")
    bad_payload = tmp_path / "payload.json"
    _index(bad_payload, [make_entry(3, library="shared", lesson={"lesson_id": "x", "payload": ["not", "an", "object"]})])
    with pytest.raises(importer.ImportAborted, match="payload"):
        importer.load_index(bad_payload)


def test_asset_sizes_are_stat_only_and_never_escape_the_root(tmp_path):
    (tmp_path / "media" / "abc").mkdir(parents=True)
    (tmp_path / "media" / "abc" / "original.mp3").write_bytes(b"x" * 10)
    assert importer.asset_size(tmp_path, "media/abc/original.mp3") == 10
    assert importer.asset_size(tmp_path, "media/abc/nope.mp3") is None
    assert importer.asset_size(tmp_path, "../etc/passwd") is None


def test_the_migration_is_proposed_not_in_versions_and_the_app_is_not_wired():
    if list((ROOT / "migrations" / "versions").glob("*0024*")):
        pytest.skip("the migration has been authorized and moved to versions/; wiring is the cutover's concern")
    assert (ROOT / "migrations" / "proposed" / "20261001_0024_media_entries.py").exists()
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "media_library_repository" not in app_source and "PostgresMediaLibraryRepository" not in app_source
    assert "FileMediaLibraryStore(_media_library_root)" in app_source, "cutover is gated: app.py still uses the file store"


# --------------------------------------------------------------------------------------------- PostgreSQL
@pytest.fixture(scope="module")
def media_engine():
    if not PG_URL:
        pytest.skip("ORENA_TEST_POSTGRES_URL is not set; PostgreSQL proof not run")
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    base = _runtime_alembic_config()
    base.set_main_option("sqlalchemy.url", PG_URL.replace("%", "%%"))
    command.upgrade(base, "head")
    with_proposed = _runtime_alembic_config()
    with_proposed.set_main_option("sqlalchemy.url", PG_URL.replace("%", "%%"))
    locations = with_proposed.get_main_option("version_locations") or str(ROOT / "migrations" / "versions")
    with_proposed.set_main_option("version_locations", f"{locations} {ROOT / 'migrations' / 'proposed'}")
    with_proposed.set_main_option("path_separator", "space")
    command.upgrade(with_proposed, "20261001_0024")
    engine = create_engine(PG_URL, future=True)
    yield engine
    engine.dispose()
    command.downgrade(with_proposed, "20260930_0023")  # leave the shared test database at the versions/ head


@pytest.fixture
def repo(media_engine):
    with media_engine.begin() as conn:
        conn.execute(text("TRUNCATE media_entry_payloads, media_entries"))
    return PostgresMediaLibraryRepository(media_engine)


def test_orm_mirror_equals_the_migrated_schema(media_engine):
    insp = inspect(media_engine)
    for table in (MediaEntry.__table__, MediaEntryPayload.__table__):
        live = {c["name"]: c for c in insp.get_columns(table.name)}
        assert set(live) == set(table.c.keys()), table.name
        for column in table.c:
            assert column.nullable == live[column.name]["nullable"], (table.name, column.name)
            kind = str(live[column.name]["type"]).upper()
            orm_kind = column.type.compile(dialect=media_engine.dialect).upper()  # the DDL PostgreSQL would get
            assert orm_kind.split("(")[0].split()[0][:4] == kind.split("(")[0].split()[0][:4], (table.name, column.name, orm_kind, kind)
            if getattr(column.type, "length", None) and hasattr(live[column.name]["type"], "length"):
                assert column.type.length == live[column.name]["type"].length, (table.name, column.name)
    live_indexes = {i["name"] for i in insp.get_indexes("media_entries")}
    assert {i.name for i in MediaEntry.__table__.indexes} <= live_indexes
    live_checks = {c["name"] for c in insp.get_check_constraints("media_entries")}
    assert {c.name for c in MediaEntry.__table__.constraints if getattr(c, "name", None) and c.name.startswith("ck_")} <= live_checks
    fks = insp.get_foreign_keys("media_entry_payloads")
    assert fks and fks[0]["options"].get("ondelete") == "CASCADE" and fks[0]["name"] == "fk_media_entry_payloads_entry"
    live_lesson_index = {i["name"]: i for i in insp.get_indexes("media_entries")}["ix_media_entries_lesson_id"]
    assert live_lesson_index["unique"] is True


def test_round_trip_head_only_get_and_payload(repo):
    entry = make_entry(1, library="shared", lesson=REAL_LESSON)
    repo.upsert(entry)
    head = repo.get(entry.media_id)
    assert head.lesson is not None and "payload" not in head.lesson and head.lesson["sections"] == ["new"]
    assert repo.get(entry.media_id, with_payload=True).lesson == REAL_LESSON
    assert repo.find_shared_by_lesson_id("media-lesson-1").media_id == entry.media_id
    assert repo.get("nope") is None


def test_upsert_cannot_flip_library_or_owner_and_keeps_created_at(repo):
    mine = make_entry(1, owner=owner_token("a"))
    repo.upsert(mine, stored_bytes=500)
    with pytest.raises(MediaEntryConflict):
        repo.upsert(make_entry(1, owner=owner_token("b")))
    repo.upsert(make_entry(1, owner=owner_token("a"), title="Renamed"))
    got = repo.get(mine.media_id)
    assert got.title == "Renamed" and got.created_at == mine.created_at
    assert repo.sum_upload_bytes(owner_token("a")) == 500, "a re-upsert without a size must keep stored_bytes"


def test_the_quota_is_atomic_per_owner_and_counts_removal_pending_rows(repo):
    owner = owner_token("quota")
    repo.insert_personal(make_entry(1, owner=owner), stored_bytes=60, byte_limit=100)
    with pytest.raises(MediaQuotaExceeded):
        repo.insert_personal(make_entry(2, owner=owner), stored_bytes=60, byte_limit=100)
    assert repo.sum_upload_bytes(owner) == 60
    repo.insert_personal(make_entry(3, owner=owner_token("other")), stored_bytes=90, byte_limit=100)  # another owner is unaffected
    repo.delete(make_entry(1, owner=owner).media_id)  # the row goes last: only now are the bytes released
    assert repo.sum_upload_bytes(owner) == 0


def test_keyset_pages_and_the_all_language_owner_walk(repo):
    owner = owner_token("walker")
    for i in range(1, 8):
        repo.upsert(make_entry(i, owner=owner, language="en" if i % 2 else "zh"), stored_bytes=1)
    seen, after = [], None
    while page := repo.list_owned_page(owner, after=after, limit=3):
        seen += [p.media_id for p in page]
        last = page[-1]
        after = (last.language, datetime.fromisoformat(last.created_at.replace("Z", "+00:00")), last.media_id)
    assert len(seen) == len(set(seen)) == 7


def test_set_status_changes_only_the_status_of_a_shared_row(repo):
    entry = make_entry(1, library="shared", lesson=REAL_LESSON)
    repo.upsert(entry)
    assert repo.set_status(entry.media_id, "archived") is True
    got = repo.get(entry.media_id, with_payload=True)
    assert got.status == "archived" and got.lesson == REAL_LESSON
    assert repo.set_status(make_entry(9, owner=owner_token("x")).media_id, "archived") is False


def test_the_import_runs_once_verifies_and_cannot_resurrect_a_deleted_upload(repo, media_engine, tmp_path):
    entries = [make_entry(1, library="shared", lesson=REAL_LESSON), make_entry(2, owner=owner_token("a")), make_entry(3, owner=None)]
    index, assets, reports = tmp_path / "index.json", tmp_path / "assets", tmp_path / "reports"
    _index(index, entries)
    for entry in entries[1:]:
        folder = assets / "media" / entry.provider_media_id
        folder.mkdir(parents=True)
        (folder / "original.mp3").write_bytes(b"a" * 100)
        (folder / "thumbnail.jpg").write_bytes(b"t" * 20)
    dry = importer.run(media_engine, index, assets, reports)
    assert dry["ok"] and repo.count() == 0
    applied = importer.run(media_engine, index, assets, reports, apply=True)
    assert applied["ok"] and applied["inserted"] == 3 and repo.sum_upload_bytes(owner_token("a")) == 120
    assert repo.get(entries[2].media_id).source.get("owner") is None  # the file's entry is reproduced verbatim
    assert repo.sum_upload_bytes(LEGACY_OWNER_TOKEN) == 120, "the legacy row is under the explicit legacy token"
    with pytest.raises(importer.ImportAborted, match="REFUSED"):
        importer.run(media_engine, index, assets, reports, apply=True)
    repo.delete(entries[1].media_id)  # a learner deletes an upload after cutover
    with pytest.raises(importer.ImportAborted):
        importer.run(media_engine, index, assets, reports, apply=True)
    assert repo.get(entries[1].media_id) is None
    assert importer.run(media_engine, index, assets, reports, verify_only=True)["ok"] is False  # it reports the difference, writes nothing
    assert repo.count() == 2


def test_database_errors_surface_as_media_store_unavailable():
    from writing_coach.persistence.media_library_repository import MediaStoreUnavailable

    dead = PostgresMediaLibraryRepository(create_engine("postgresql+psycopg://x:y@127.0.0.1:1/none", connect_args={"connect_timeout": 1}))
    for call in (lambda: dead.get("a"), lambda: dead.delete("a"), lambda: dead.sum_upload_bytes("o")):
        with pytest.raises(MediaStoreUnavailable):
            call()
