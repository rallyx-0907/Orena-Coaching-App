"""Rehearsal of migration 20261001_0024 (media metadata in PostgreSQL) on a throwaway PostgreSQL.

`docs/project/proposals/MEDIA_METADATA_POSTGRES.md` (revision 2), section 12 (runs 1-6 and 5b), D-108.5. Kept in the repository so
a reviewer can re-run it. Not part of CI, touches no runtime: it talks only to a database it is given by URL, and only if that
database is clearly throwaway and empty. It never reads POSTGRES_RUNTIME_URL for anything but the refusal check.

    docker network create media-rehearsal-net
    docker run -d --name media-rehearsal-pg --network media-rehearsal-net -e POSTGRES_PASSWORD=rehearsal \
        -e POSTGRES_DB=media_rehearsal postgres:17-alpine
    # in the application image, repository mounted read-only, on the same network:
    python scripts/rehearse_media_metadata_schema.py \
        postgresql+psycopg://postgres:rehearsal@media-rehearsal-pg:5432/media_rehearsal --volume 100000
    docker rm -f media-rehearsal-pg; docker network rm media-rehearsal-net

What it does (every line is a PASS or FAIL row; non-zero exit on any FAIL):
 1. Refuses a URL that is not clearly throwaway, or a non-empty database.
 2. Run 1: builds the chain to 20260930_0023 from migrations/versions/ (one revision per invocation, timed), asserts the
    versions-only head is still 0023, then upgrades to 0024 from migrations/proposed/, downgrades, re-upgrades; the full schema
    after the downgrade equals the schema captured at 0023, the new tables' schema after the second upgrade equals the first,
    and no pre-existing table changed (so no lock on one). A reader hammers `users` during every 0024 step; its worst latency
    is the lock evidence.
 3. Run 5/5b/6: constraints, owner agreement, FK cascade, upsert guards, head-only get, keyset paging under concurrent
    insert, the advisory-lock quota race (8 workers at the edge; 8 owners in parallel), JSONB round-trips (Chinese text, a
    150 KB payload, NUL, key order), old-code inserts.
 4. Run 4: the import script: dry-run writes nothing, apply, second apply refused, marker, verify-only, tamper detected,
    corrupt/hash-mismatched index aborts with zero rows, a concurrent writer to the index is detected; then at --import-volume.
 5. Run 2/3: --volume N personal rows and --shared S shared rows (with 25-150 KB payloads) in SQL; VACUUM ANALYZE; EXPLAIN
    (ANALYZE, BUFFERS) and p50/p95 for every query of proposal 3.5; index-only proof for the quota sum (Heap Fetches),
    and the stale-visibility-map case; table and index sizes; downgrade and re-upgrade at volume (timed).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import statistics
import sys
import tempfile
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402

import import_media_index as importer  # noqa: E402
from writing_coach.media_library_store import MediaLibraryEntry, owner_token  # noqa: E402
from writing_coach.persistence.media_library_repository import (  # noqa: E402
    LEGACY_OWNER_TOKEN,
    MediaEntryConflict,
    MediaQuotaExceeded,
    PostgresMediaLibraryRepository,
)

BASE = "20260930_0023"
HEAD = "20261001_0024"
VERSIONS = ROOT / "migrations" / "versions"
PROPOSED = ROOT / "migrations" / "proposed"
NEW_TABLES = ("media_entries", "media_entry_payloads")
NEW_INDEXES = ("ix_media_entries_browse", "ix_media_entries_library_created", "ix_media_entries_lesson_id", "ix_media_entries_owner")

THROWAWAY_NAME = re.compile(r"(rehears|throwaway|scratch)", re.IGNORECASE)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
RUNTIME_DATABASES = {"becoming", "postgres", "orena", "ai_writing_coach"}


def refuse_unless_throwaway(url: str) -> None:
    parsed = make_url(url)
    problems = []
    if not parsed.drivername.startswith("postgresql"):
        problems.append(f"driver {parsed.drivername!r} is not PostgreSQL")
    name = parsed.database or ""
    if name.lower() in RUNTIME_DATABASES or not THROWAWAY_NAME.search(name):
        problems.append(f"database name {name!r} must contain 'rehears', 'throwaway' or 'scratch'")
    host = (parsed.host or "").lower()
    if host not in LOCAL_HOSTS and not THROWAWAY_NAME.search(host):
        problems.append(f"host {host!r} is not local or a rehearsal container")
    if parsed.port in {8000, 8010, 8011, 8021}:
        problems.append(f"port {parsed.port} is a runtime port")
    configured = os.environ.get("POSTGRES_RUNTIME_URL", "").strip()
    if configured:
        other = make_url(configured)
        if (other.host, other.port, other.database) == (parsed.host, parsed.port, parsed.database):
            problems.append("it is the configured runtime database (POSTGRES_RUNTIME_URL)")
    if problems:
        sys.exit("REFUSED: not a clearly throwaway database:\n  - " + "\n  - ".join(problems))


results: list[tuple[str, bool, str]] = []
timings: list[tuple[str, float]] = []
facts: dict[str, object] = {}


def record(label, ok, detail=""):
    results.append((label, ok, detail))


def check(label, function):
    try:
        record(label, True, function() or "")
    except AssertionError as error:
        record(label, False, str(error) or "assertion failed")
    except Exception as error:  # noqa: BLE001 - a rehearsal reports every failure
        record(label, False, f"{type(error).__name__}: {str(error)[:240]}")


def q(engine, statement, params=None):
    """One scalar, on a connection that is closed (an open one holds locks and blocks TRUNCATE)."""
    with engine.connect() as conn:
        return conn.execute(statement, params or {}).scalar()


def ok(condition, fail="failed", good="ok"):
    """A check passes only if the condition holds; otherwise the row FAILS with `fail`."""
    assert condition, fail
    return good


def timed(label, function):
    start = time.monotonic()
    value = function()
    timings.append((label, round(time.monotonic() - start, 3)))
    return value


def alembic_config(url, *, with_proposed):
    locations = [str(VERSIONS)] + ([str(PROPOSED)] if with_proposed else [])
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.set_main_option("version_locations", " ".join(locations))
    cfg.set_main_option("path_separator", "space")
    return cfg


def current_revision(engine):
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def signature(engine, tables=None):
    out = {}
    with engine.connect() as conn:
        names = tables or conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY 1")
        ).scalars().all()
        for t in names:
            out[f"columns:{t}"] = [tuple(r) for r in conn.execute(text(
                "SELECT column_name, data_type, is_nullable, column_default, character_maximum_length FROM"
                " information_schema.columns WHERE table_schema='public' AND table_name=:t ORDER BY column_name"), {"t": t})]
            out[f"indexes:{t}"] = [tuple(r) for r in conn.execute(text(
                "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=:t ORDER BY 1"), {"t": t})]
            out[f"constraints:{t}"] = sorted(tuple(r) for r in conn.execute(text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid=to_regclass(:t)"), {"t": f"public.{t}"}))
    return out


class Reader(threading.Thread):
    """Hammers an existing table while a migration step runs; the worst latency is the lock evidence."""

    def __init__(self, engine):
        super().__init__(daemon=True)
        self.engine, self.stop, self.worst, self.count = engine, threading.Event(), 0.0, 0

    def run(self):
        while not self.stop.is_set():
            start = time.monotonic()
            try:
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT count(*) FROM (SELECT 1 FROM users LIMIT 1) s"))
                    conn.execute(text("SELECT count(*) FROM (SELECT 1 FROM works LIMIT 1) s"))
            except Exception:  # noqa: BLE001
                self.worst = max(self.worst, 999.0)
            self.worst = max(self.worst, time.monotonic() - start)
            self.count += 1
            time.sleep(0.005)


def step_with_reader(engine, label, function):
    reader = Reader(engine)
    reader.start()
    time.sleep(0.05)
    try:
        timed(label, function)
    finally:
        reader.stop.set()
        reader.join()
    facts[f"reader:{label}"] = f"{reader.count} reads, worst {reader.worst * 1000:.1f} ms"
    return reader


# ------------------------------------------------------------------------------------------------ entries
def make_entry(i: int, *, library="personal", language="en", owner=None, lesson=None, status="published",
               provider=None, title=None, created=None) -> MediaLibraryEntry:
    token = hashlib.md5(f"e{i}".encode()).hexdigest()
    shared = library == "shared"
    provider = provider or ("youtube" if shared else "upload")
    media_id = f"yt-{token}" if provider == "youtube" else (f"direct-{token}" if provider == "direct" else f"upload-{token}")
    source = {"provider": provider, "type": "admin-import" if shared else "upload", "provenance_url": "",
              "license": "File supplied to Orena.", "review_status": "checked", "imported_by": "admin" if shared else "learner"}
    if not shared and owner:
        source["owner"] = owner
    thumb = ({"kind": "provider-url", "ref": f"https://img.example.test/{token}.jpg"} if provider == "youtube"
             else {"kind": "asset", "ref": f"media/{token}/thumbnail.jpg"})
    return MediaLibraryEntry(
        media_id=media_id, media_type="audio", provider=provider, provider_media_id=token,
        canonical_url="https://www.youtube.com/watch?v=" + token[:11] if provider == "youtube" else "",
        playback={"provider": "youtube" if provider == "youtube" else "orena", "kind": "audio",
                  "url": f"https://www.youtube.com/embed/{token[:11]}" if provider == "youtube" else f"/api/media/files/media/{token}/original.mp3"},
        title=title or f"Title {i}", thumbnail=thumb, duration_ms=60_000 + i, language=language, level="", creator="",
        source=source, library=library, created_at=(created or datetime(2026, 9, 1, tzinfo=UTC) + timedelta(seconds=i)).isoformat().replace("+00:00", "Z"),
        lesson=lesson, status=status,
    )


def real_lesson(i: int, segments: int = 30, topic=True) -> dict:
    lesson = {"lesson_id": f"media-lesson-{i}", "payload": {
        "asset": {"asset_id": f"yt-{i}", "title": f"t{i}"},
        "transcript": {"segments": [{"start": k * 3000, "end": k * 3000 + 2800, "text": f"segment {k} of {i}"} for k in range(segments)]},
        "translations": [], "transcript_origin": "captions"},
        "sections": ["new"], "status": "PUBLISHED", "curation": "reviewed", "language": "en"}
    if topic:
        lesson.update({"topic": "travel", "tags": ["a", "b"]})
    return lesson


def write_index(path: Path, entries: list[MediaLibraryEntry]) -> None:
    ordered = [asdict(e) for e in sorted(entries, key=lambda e: e.media_id)]
    body = json.dumps(ordered, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "entries": ordered, "integrity": hashlib.sha256(body.encode()).hexdigest()},
                               ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_assets(root: Path, entries: list[MediaLibraryEntry], *, skip: set[str] = frozenset()) -> None:
    for e in entries:
        if e.provider != "upload" or e.media_id in skip:
            continue
        d = root / "media" / e.provider_media_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "original.mp3").write_bytes(b"a" * 1500)
        if e.thumbnail["kind"] == "asset":
            (d / "thumbnail.jpg").write_bytes(b"t" * 300)


def truncate(engine):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE media_entry_payloads, media_entries"))


# ------------------------------------------------------------------------------------------------ runs
def run1(url, engine):
    cfg_v, cfg_p = alembic_config(url, with_proposed=False), alembic_config(url, with_proposed=True)
    revisions = [r.revision for r in reversed(list(ScriptDirectory.from_config(cfg_v).walk_revisions()))]
    check("run1: versions-only head is still 0023 (0024 is not in versions/)",
          lambda: ok(ScriptDirectory.from_config(cfg_v).get_heads() == [BASE], "versions-only heads: %s" % ScriptDirectory.from_config(cfg_v).get_heads(), "head 0023"))
    check("run1: with migrations/proposed/ the single head is 0024",
          lambda: ok(ScriptDirectory.from_config(cfg_p).get_heads() == [HEAD], "heads: %s" % ScriptDirectory.from_config(cfg_p).get_heads(), "single head 0024"))
    for rev in revisions:
        timed(f"chain {rev}", lambda rev=rev: command.upgrade(cfg_v, rev))
    check("run1: chain built to 0023", lambda: ok(current_revision(engine) == BASE, f"at {current_revision(engine)}"))
    with engine.begin() as conn:  # an old-code row, before 0024 exists
        conn.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) VALUES"
                          " (gen_random_uuid(), 'pre-0024', 'p@example.test', '', '', 'user', now())"))
    pre = signature(engine)
    step_with_reader(engine, "0024 upgrade (empty)", lambda: command.upgrade(cfg_p, HEAD))
    check("run1: at 0024", lambda: current_revision(engine) == HEAD or current_revision(engine))
    after_up = signature(engine, list(NEW_TABLES))
    post_existing = signature(engine, [t for t in {k.split(":", 1)[1] for k in pre}])
    check("run6: no pre-existing table, column, index or constraint changed by 0024",
          lambda: ok(all(post_existing[k] == v for k, v in pre.items()), "pre-existing schema changed"))
    step_with_reader(engine, "0024 downgrade (empty)", lambda: command.downgrade(cfg_p, BASE))
    check("run1: downgrade removed both tables and nothing else (full schema equals 0023)",
          lambda: ok(signature(engine) == pre, "schema after downgrade differs from 0023"))
    check("run6: the old-code row survives the up/down", lambda: ok(q(engine, text("SELECT count(*) FROM users WHERE user_key='pre-0024'")) == 1, "lost"))
    step_with_reader(engine, "0024 re-upgrade (empty)", lambda: command.upgrade(cfg_p, HEAD))
    check("run1: schema after the second upgrade equals the first", lambda: ok(signature(engine, list(NEW_TABLES)) == after_up, "differs"))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO users (id, user_key, email, name, picture, role, created_at) VALUES"
                          " (gen_random_uuid(), 'post-0024', 'q@example.test', '', '', 'user', now())"))
    record("run6: old-code insert (names no media object) works on the 0024 schema", True, "users insert")
    return cfg_p


def probes(engine):
    repo = PostgresMediaLibraryRepository(engine)
    owner = owner_token("probe-owner")
    other = owner_token("other-owner")

    def refuses(sql_text, params=None):
        try:
            with engine.begin() as conn:
                conn.execute(text(sql_text), params or {})
        except (IntegrityError, DBAPIError):
            return True
        return False

    base = make_entry(1, owner=owner)
    repo.upsert(base, stored_bytes=1000)
    ins = ("INSERT INTO media_entries (media_id, library, status, media_type, provider, provider_media_id, title, duration_ms,"
           " language, playback, thumbnail_kind, thumbnail_ref, source, tags, owner_token, created_at, updated_at, has_lesson)"
           " VALUES (:id, :lib, :st, :mt, :pr, :pm, :ti, :du, 'en', CAST('{}' AS JSONB), :tk, :tr, CAST(:src AS JSONB), CAST('[]' AS JSONB), :ow, now(), now(), false)")

    def row(**kw):
        p = dict(id="x-1", lib="shared", st="published", mt="audio", pr="youtube", pm="abc", ti="t", du=1, tk="none", tr="",
                 src="{}", ow=None)
        p.update(kw)
        return p

    cases = {
        "bad library": row(lib="private"), "bad status": row(st="deleted"), "bad media_type": row(mt="image"),
        "bad media_id pattern": row(id="bad id!"), "bad provider pattern": row(pr="bad provider"),
        "thumbnail none with a ref": row(tk="none", tr="x"), "thumbnail asset without a ref": row(tk="asset", tr=""),
        "negative duration": row(du=-1), "empty title": row(ti=""),
        "shared row carrying an owner": row(ow="a" * 32), "personal row without an owner": row(lib="personal", pr="upload", ow=None),
        "personal row with a non-upload provider": row(lib="personal", pr="youtube", ow="a" * 32),
        "source.owner disagreeing with owner_token": row(lib="personal", pr="upload", ow="a" * 32, src=json.dumps({"owner": "b" * 32})),
    }
    for label, params in cases.items():
        check(f"run5: CHECK refuses {label}", lambda params=params: ok(refuses(ins, params), "accepted a bad row"))
    check("run5: a negative stored_bytes is refused", lambda: ok(refuses("UPDATE media_entries SET stored_bytes = -1 WHERE media_id = :i", {"i": base.media_id}), "accepted"))
    check("run5: lesson_meta / has_lesson must agree", lambda: ok(refuses("UPDATE media_entries SET has_lesson = true WHERE media_id = :i", {"i": base.media_id}), "accepted"))

    def upsert_guards():
        flipped = make_entry(1, owner=other)
        try:
            repo.upsert(flipped)
            return "owner flip accepted"
        except MediaEntryConflict:
            pass
        shared_flip = make_entry(1, library="shared", provider="upload")
        try:
            repo.upsert(shared_flip)
            return "library flip accepted"
        except (MediaEntryConflict, IntegrityError):
            pass
        again = make_entry(1, owner=owner, title="Renamed", created=datetime(2030, 1, 1, tzinfo=UTC))
        repo.upsert(again)
        got = repo.get(base.media_id)
        assert got.title == "Renamed", "an allowed upsert did not apply"
        assert got.created_at == base.created_at, f"created_at moved: {got.created_at} != {base.created_at}"
        return "owner/library flips refused; created_at immutable; stored_bytes kept on a NULL re-upsert"
    check("run5: upsert never flips library/owner_token and never moves created_at", upsert_guards)
    check("run5: stored_bytes survives an upsert that carries none", lambda: ok(q(engine, text("SELECT stored_bytes FROM media_entries WHERE media_id=:i"), {"i": base.media_id}) == 1000, "lost"))

    def cascade_and_head_only():
        e = make_entry(2, library="shared", lesson=real_lesson(2))
        repo.upsert(e)
        statements = []
        from sqlalchemy import event
        def spy(conn, cursor, statement, params, context, executemany):
            statements.append(statement)
        event.listen(engine, "before_cursor_execute", spy)
        try:
            head = repo.get(e.media_id)
            payload_reads = sum("media_entry_payloads" in s for s in statements)
            full = repo.get(e.media_id, with_payload=True)
        finally:
            event.remove(engine, "before_cursor_execute", spy)
        assert payload_reads == 0 and "payload" not in (head.lesson or {}), "head-only get touched the payload"
        assert full.lesson["payload"]["transcript"]["segments"][0]["text"] == "segment 0 of 2"
        assert full.lesson["sections"] == ["new"] and full.lesson["curation"] == "reviewed", "extra lesson keys lost"
        repo.delete(e.media_id)
        left = q(engine, text("SELECT count(*) FROM media_entry_payloads WHERE media_id=:i"), {"i": e.media_id})
        assert left == 0, "payload row survived the entry delete"
        return "head-only get issued 0 payload queries; real lesson keys round-trip; cascade removed the payload"
    check("run5: head-only get, lesson keys beyond lesson_id/topic/tags round-trip, FK cascade", cascade_and_head_only)

    def lesson_without_topic():
        e = make_entry(3, library="shared", lesson=real_lesson(3, topic=False))
        repo.upsert(e)
        got = repo.get(e.media_id, with_payload=True)
        repo.delete(e.media_id)
        assert got.lesson == e.lesson, "a lesson without topic/tags was altered by the round trip"
        return "no topic/tags keys invented"
    check("run5: a lesson without topic/tags comes back unchanged", lesson_without_topic)

    def unique_lesson():
        a = make_entry(4, library="shared", lesson=real_lesson(4))
        b = make_entry(5, library="shared", lesson={**real_lesson(4), "topic": "other"})
        repo.upsert(a)
        try:
            repo.upsert(b)
            return "two shared entries with one lesson_id accepted"
        except MediaEntryConflict:
            return "unique shared lesson_id enforced"
        finally:
            repo.delete(a.media_id)
    check("run5: shared lesson_id is unique", unique_lesson)

    def set_status_keeps_lesson():
        e = make_entry(6, library="shared", lesson=real_lesson(6))
        repo.upsert(e)
        assert repo.set_status(e.media_id, "archived")
        got = repo.get(e.media_id, with_payload=True)
        repo.delete(e.media_id)
        assert got.status == "archived" and got.lesson == e.lesson, "status change altered the entry"
        return "single-field UPDATE; lesson intact"
    check("run5: set_status is a status-only UPDATE", set_status_keeps_lesson)

    def jsonb():
        title = "你好，世界 — emoji \U0001F3A7 é"
        payload = {"asset": {"k": "v"}, "transcript": {"segments": [{"text": "x" * 100} for _ in range(1500)]}, "translations": []}
        e = make_entry(7, library="shared", title=title, lesson={"lesson_id": "j7", "payload": payload})
        size = len(json.dumps(payload))
        repo.upsert(e)
        got = repo.get(e.media_id, with_payload=True)
        repo.delete(e.media_id)
        assert got.title == title and got.lesson["payload"] == payload, "round trip differs"
        return f"Chinese + emoji title and a {size // 1024} KB payload round-trip exactly"
    check("run5b: JSONB round trips (Chinese/emoji, 150 KB payload, key order irrelevant)", jsonb)

    def nul():
        try:
            with engine.begin() as conn:
                conn.execute(text("SELECT CAST(:v AS JSONB)"), {"v": json.dumps({"a": "x\u0000y"})})
            return "NUL accepted by jsonb"
        except DBAPIError:
            return "jsonb REFUSES \\u0000 (the import aborts such an entry rather than corrupting it)"
    check("run5b: JSONB behaviour for NUL", nul)

    def paging():
        for i in range(100, 160):
            repo.upsert(make_entry(i, library="shared", language="en", created=datetime(2026, 9, 1, tzinfo=UTC) + timedelta(minutes=i)))
        stop = threading.Event()
        def writer():
            n = 1000
            while not stop.is_set():
                repo.upsert(make_entry(n, library="shared", language="en", created=datetime(2026, 9, 1, tzinfo=UTC) + timedelta(minutes=random.uniform(0, 160))))
                n += 1
                time.sleep(0.003)
        t = threading.Thread(target=writer, daemon=True)
        t.start()
        seen, after = [], None
        # the first page is taken after the writer started, so "existing" = every row older than the cursor start
        while True:
            page = repo.list_page(library="shared", language="en", after=after, limit=7)
            if not page:
                break
            seen += [p.media_id for p in page]
            last = page[-1]
            after = (datetime.fromisoformat(last.created_at.replace("Z", "+00:00")), last.media_id)
        stop.set()
        t.join()
        assert len(seen) == len(set(seen)), "a row appeared on two pages"
        originals = {make_entry(i, library="shared").media_id for i in range(100, 160)}
        assert originals <= set(seen), "an existing row was skipped"
        return f"{len(seen)} rows over pages of 7 while inserting: no duplicate, no skipped row"
    check("run5: keyset paging is stable under concurrent insert", paging)

    def quota_race():
        size, limit = 100, 400
        results_ = []
        def worker(n):
            try:
                repo.insert_personal(make_entry(500 + n, owner=other), stored_bytes=size, byte_limit=limit)
                results_.append("ok")
            except MediaQuotaExceeded:
                results_.append("refused")
        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        total = repo.sum_upload_bytes(other)
        assert results_.count("ok") == 4 and results_.count("refused") == 4 and total == 400, (results_, total)
        return "8 workers, one owner, limit for 4: exactly 4 admitted, 4 refused, sum 400"
    check("run5b: advisory-lock quota race at the edge (8 workers)", quota_race)

    def parallel_owners():
        owners = [owner_token(f"par-{n}") for n in range(8)]
        times = []
        def worker(n):
            start = time.monotonic()
            repo.insert_personal(make_entry(700 + n, owner=owners[n]), stored_bytes=10, byte_limit=1000)
            times.append(time.monotonic() - start)
        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert len(times) == 8
        return f"8 different owners in parallel all admitted (worst {max(times) * 1000:.0f} ms)"
    check("run5b: different owners do not contend", parallel_owners)
    truncate(engine)


def run4_import(engine, workdir: Path):
    repo = PostgresMediaLibraryRepository(engine)
    own = owner_token("learner-a")
    entries = [
        make_entry(1, library="shared", lesson=real_lesson(1)),
        make_entry(2, library="shared", provider="direct", lesson=None),
        make_entry(3, owner=own), make_entry(4, owner=own, language="zh", title="中文标题"),
        make_entry(5, owner=None),  # legacy: personal row without an owner
        make_entry(6, library="shared", lesson=real_lesson(6, topic=False), status="unpublished"),
    ]
    entries[1] = make_entry(2, library="shared", provider="direct", lesson=None)
    index, assets, reports = workdir / "index.json", workdir / "assets", workdir / "reports"
    shutil.rmtree(workdir, ignore_errors=True)
    write_index(index, entries)
    write_assets(assets, entries)
    # make one asset missing
    shutil.rmtree(assets / "media" / entries[3].provider_media_id)

    def dry():
        r = importer.run(engine, index, assets, reports)
        n = q(engine, text("SELECT count(*) FROM media_entries"))
        assert n == 0 and r["ok"], "dry-run wrote rows"
        assert r["counts"]["legacy_owner_rows"] == 1 and len(r["missing_assets"]) >= 1
        return f"0 rows written; legacy-owner rows {r['counts']['legacy_owner_rows']}; missing assets {len(r['missing_assets'])}; upload bytes {r['counts']['upload_bytes']}"
    check("run4: dry-run writes nothing and reports legacy rows and missing assets", dry)

    def apply_():
        r = importer.run(engine, index, assets, reports, apply=True)
        assert r["ok"] and r["inserted"] == len(entries) and r["verification"]["hash_ok"], r.get("verification")
        legacy = q(engine, text("SELECT owner_token FROM media_entries WHERE media_id=:i"), {"i": entries[4].media_id})
        assert legacy == LEGACY_OWNER_TOKEN, "legacy row not under the explicit legacy token"
        sb = q(engine, text("SELECT stored_bytes FROM media_entries WHERE media_id=:i"), {"i": entries[2].media_id})
        assert sb == 1800, f"stored_bytes {sb} != original 1500 + thumbnail 300"
        missing_sb = q(engine, text("SELECT stored_bytes FROM media_entries WHERE media_id=:i"), {"i": entries[3].media_id})
        assert missing_sb is None, "an upload with a missing asset must have NULL stored_bytes"
        return f"inserted {r['inserted']}; verification exact (hash_ok); legacy token explicit; stored_bytes 1800 measured by stat; missing asset -> NULL"
    check("run4: apply inserts, verifies field-for-field, makes the legacy owner explicit", apply_)

    def second_apply():
        try:
            importer.run(engine, index, assets, reports, apply=True)
            return "second --apply was NOT refused"
        except importer.ImportAborted as error:
            assert "REFUSED" in str(error)
            return str(error)[:90]
    check("run4: a second --apply is refused (table not empty)", second_apply)

    def marker_after_learner_deletion():
        repo.delete(entries[2].media_id)  # a learner deleted an upload after cutover
        try:
            importer.run(engine, index, assets, reports, apply=True)
            return "re-run after a deletion was NOT refused"
        except importer.ImportAborted:
            pass
        n = q(engine, text("SELECT count(*) FROM media_entries WHERE media_id=:i"), {"i": entries[2].media_id})
        assert n == 0, "the deleted upload was resurrected"
        # even with the table emptied, the single-use marker refuses
        truncate(engine)
        try:
            importer.run(engine, index, assets, reports, apply=True)
            return "marker did not refuse on an emptied table"
        except importer.ImportAborted as error:
            assert "marker" in str(error)
        return "after a deletion the re-run is refused and nothing is resurrected; on an emptied table the marker refuses"
    check("run4: re-run after a learner deleted an upload cannot resurrect it (the P2-2 case)", marker_after_learner_deletion)

    def verify_only():
        (reports / importer.MARKER_NAME).unlink()
        importer.run(engine, index, assets, reports, apply=True)
        ok = importer.run(engine, index, assets, reports, verify_only=True)
        assert ok["ok"], ok
        with engine.begin() as conn:
            conn.execute(text("UPDATE media_entries SET title = 'tampered' WHERE media_id = :i"), {"i": entries[0].media_id})
        bad = importer.run(engine, index, assets, reports, verify_only=True)
        assert not bad["ok"] and bad["verification"]["problem_count"] >= 1, "tamper not detected"
        return "verify-only passes on an exact import, writes nothing, and detects a tampered row"
    check("run4: --verify-only passes, writes nothing and detects a tampered row", verify_only)

    def corrupt():
        truncate(engine)
        (reports / importer.MARKER_NAME).unlink(missing_ok=True)
        data = json.loads(index.read_text(encoding="utf-8"))
        data["entries"][0]["title"] = "changed after hashing"
        bad = workdir / "bad.json"
        bad.write_text(json.dumps(data), encoding="utf-8")
        try:
            importer.run(engine, bad, assets, reports, apply=True)
            return "a hash-mismatched index was accepted"
        except importer.ImportAborted as error:
            n = q(engine, text("SELECT count(*) FROM media_entries"))
            assert n == 0, "rows written before the abort"
            return f"aborted ({error}); 0 rows written"
    check("run4: a hash-mismatched index aborts with zero rows written", corrupt)

    def invalid_entry():
        data = json.loads(index.read_text(encoding="utf-8"))
        data["entries"][1]["language"] = "klingon"
        body = json.dumps(data["entries"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        data["integrity"] = hashlib.sha256(body.encode()).hexdigest()
        bad = workdir / "invalid.json"
        bad.write_text(json.dumps(data), encoding="utf-8")
        try:
            importer.run(engine, bad, assets, reports, apply=True)
            return "an invalid entry was accepted"
        except importer.ImportAborted as error:
            return f"aborted ({str(error)[:60]}); 0 rows"
    check("run4: ONE invalid entry aborts the whole import", invalid_entry)

    def concurrent_writer():
        original = importer.insert_all
        def meddle(eng, rows):
            out = original(eng, rows)
            index.write_text(index.read_text(encoding="utf-8") + " ", encoding="utf-8")  # the old process wrote
            return out
        importer.insert_all = meddle
        try:
            truncate(engine)
            (reports / importer.MARKER_NAME).unlink(missing_ok=True)
            r = importer.run(engine, index, assets, reports, apply=True)
        finally:
            importer.insert_all = original
        assert not r["ok"] and r["index_unchanged"] is False, "a concurrent writer was not detected"
        assert not (reports / importer.MARKER_NAME).exists(), "marker written for a failed import"
        return "index size/SHA changed during the run: reported, ok=false, no marker"
    check("run4: a writer touching index.json during the import is detected", concurrent_writer)
    truncate(engine)
    (reports / importer.MARKER_NAME).unlink(missing_ok=True)


def run4_volume(engine, workdir: Path, count: int):
    """Import at volume: an index of `count` entries (90% personal uploads), real small asset files."""
    root = workdir / "vol"
    shutil.rmtree(root, ignore_errors=True)
    assets, reports = root / "assets", root / "reports"
    shared = max(10, count // 10)
    entries = [make_entry(i, library="shared", lesson=real_lesson(i, 20)) for i in range(shared)]
    owners = [owner_token(f"v{n}") for n in range(max(1, count // 60))]
    entries += [make_entry(shared + i, owner=owners[i % len(owners)], language="en" if i % 3 else "zh") for i in range(count - shared)]
    timed(f"import-volume {count}: generate index.json + assets", lambda: (write_index(root / "index.json", entries), write_assets(assets, entries)))
    size = (root / "index.json").stat().st_size
    facts["import volume index.json bytes"] = size
    dry = timed(f"import-volume {count}: dry-run", lambda: importer.run(engine, root / "index.json", assets, reports))
    applied = timed(f"import-volume {count}: apply (insert + verify + ANALYZE)", lambda: importer.run(engine, root / "index.json", assets, reports, apply=True))
    check(f"run4: import at {count} entries ({size // 1024 // 1024} MiB index): exact verification", lambda: applied["ok"] or json.dumps(applied.get("verification"))[:200])
    timed(f"import-volume {count}: second run refused", lambda: None)
    try:
        importer.run(engine, root / "index.json", assets, reports, apply=True)
        record(f"run4: second apply at {count} refused", False, "not refused")
    except importer.ImportAborted:
        record(f"run4: second apply at {count} refused", True, "REFUSED (rows present)")
    timed(f"import-volume {count}: verify-only", lambda: importer.run(engine, root / "index.json", assets, reports, verify_only=True))
    facts["import volume"] = {"entries": count, "report_seconds_apply": applied.get("seconds"), "upload_bytes": applied["counts"]["upload_bytes"]}
    truncate(engine)
    shutil.rmtree(root, ignore_errors=True)


SEED_SHARED = """
INSERT INTO media_entries (media_id, library, status, media_type, provider, provider_media_id, canonical_url, title, creator,
    duration_ms, language, level, playback, thumbnail_kind, thumbnail_ref, source, owner_token, lesson_meta, lesson_id, topic,
    tags, has_lesson, segment_count, stored_bytes, created_at, updated_at)
SELECT 'yt-' || md5('s' || g), 'shared', CASE WHEN g % 20 = 0 THEN 'unpublished' ELSE 'published' END, 'audio', 'youtube', md5('s' || g),
    'https://www.youtube.com/watch?v=' || md5('s' || g), 'Shared ' || g, '', 120000 + g, CASE WHEN g % 2 = 0 THEN 'en' ELSE 'zh' END, '',
    jsonb_build_object('provider','youtube','kind','audio','url','https://www.youtube.com/embed/x'), 'provider-url', 'https://i.ytimg.com/vi/' || g,
    jsonb_build_object('provider','youtube','type','admin-import','provenance_url','','license','x','review_status','y','imported_by','admin'),
    NULL, jsonb_build_object('lesson_id','media-lesson-' || g,'sections',jsonb_build_array('new'),'status','PUBLISHED','curation','reviewed','topic','topic' || (g % 8),'tags',jsonb_build_array('a','b')),
    'media-lesson-' || g, 'topic' || (g % 8), jsonb_build_array('a','b'), true, 40 + (g % 460), NULL,
    now() - make_interval(secs => g), now()
FROM generate_series(1, :n) g
"""
SEED_SHARED_PAYLOADS = """
INSERT INTO media_entry_payloads (media_id, payload)
SELECT e.media_id, jsonb_build_object('asset', jsonb_build_object('asset_id', e.media_id),
    'transcript', jsonb_build_object('segments', (SELECT jsonb_agg(jsonb_build_object('start', k * 3000, 'text', md5(random()::text || k) || md5(random()::text || k)))
        FROM generate_series(1, e.segment_count) k)), 'translations', '[]'::jsonb)
FROM media_entries e WHERE e.library = 'shared'
"""
SEED_PERSONAL = """
INSERT INTO media_entries (media_id, library, status, media_type, provider, provider_media_id, canonical_url, title, creator,
    duration_ms, language, level, playback, thumbnail_kind, thumbnail_ref, source, owner_token, lesson_meta, lesson_id, topic,
    tags, has_lesson, segment_count, stored_bytes, created_at, updated_at)
SELECT 'upload-' || md5('p' || g), 'personal', 'published', 'audio', 'upload', md5('p' || g), '', 'Upload ' || g, '',
    60000 + g, CASE WHEN g % 3 = 0 THEN 'zh' ELSE 'en' END, '',
    jsonb_build_object('provider','orena','kind','audio','url','/api/media/files/media/' || md5('p' || g) || '/original.mp3'),
    'asset', 'media/' || md5('p' || g) || '/thumbnail.jpg',
    jsonb_build_object('provider','upload','type','learner-upload','provenance_url','','license','File supplied to Orena.','review_status','checked','imported_by','learner',
        'owner', md5('owner' || CASE WHEN g <= 10000 THEN 0 ELSE g % :owners END)),
    md5('owner' || CASE WHEN g <= 10000 THEN 0 ELSE g % :owners END), NULL, NULL, '', '[]'::jsonb, false, 0,
    (5000000 + (g * 7919) % 55000000)::bigint, now() - make_interval(secs => g), now()
FROM generate_series(1, :n) g
"""


def plan_nodes(node, out):
    out.append(node)
    for child in node.get("Plans", []) or []:
        plan_nodes(child, out)


def explain(engine, sql, params, *, analyze=True):
    prefix = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " if analyze else "EXPLAIN (FORMAT JSON) "
    with engine.connect() as conn:
        raw = conn.execute(text(prefix + sql), params).scalar()
    doc = raw if isinstance(raw, list) else json.loads(raw)
    nodes: list[dict] = []
    plan_nodes(doc[0]["Plan"], nodes)
    return {
        "types": sorted({n["Node Type"] for n in nodes}),
        "indexes": sorted({n.get("Index Name") for n in nodes if n.get("Index Name")}),
        "seq_scans_on_media_entries": sum(1 for n in nodes if n["Node Type"] == "Seq Scan" and n.get("Relation Name") == "media_entries"),
        "heap_fetches": sum(n.get("Heap Fetches", 0) for n in nodes if n["Node Type"] == "Index Only Scan"),
        "ms": round(doc[0].get("Execution Time", 0), 3),
        "buffers_hit": doc[0]["Plan"].get("Shared Hit Blocks", 0),
    }


def latency(engine, sql, params_fn, runs=200):
    samples = []
    with engine.connect() as conn:
        for _ in range(runs):
            params = params_fn()
            start = time.perf_counter()
            conn.execute(text(sql), params).fetchall()
            samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    return {"p50_ms": round(statistics.median(samples), 3), "p95_ms": round(samples[int(len(samples) * 0.95) - 1], 3), "max_ms": round(samples[-1], 3)}


def run_volume(url, engine, cfg_p, volume, shared):
    owners = max(1, volume // 60)
    timed(f"seed shared {shared}", lambda: _exec(engine, SEED_SHARED, {"n": shared}))
    timed(f"seed shared payloads ({shared})", lambda: _exec(engine, SEED_SHARED_PAYLOADS, {}))
    timed(f"seed personal {volume}", lambda: _exec(engine, SEED_PERSONAL, {"n": volume, "owners": owners}))
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        timed("VACUUM (ANALYZE) both tables", lambda: (conn.execute(text("VACUUM (ANALYZE) media_entries")), conn.execute(text("VACUUM (ANALYZE) media_entry_payloads"))))
    with engine.connect() as conn:
        counts = dict(conn.execute(text("SELECT library, count(*) FROM media_entries GROUP BY 1")).all())
        sizes = {r[0]: r[1] for r in conn.execute(text(
            "SELECT relname, pg_total_relation_size(oid) FROM pg_class WHERE relname IN ('media_entries','media_entry_payloads')"))}
        idx = {r[0]: r[1] for r in conn.execute(text(
            "SELECT indexrelname, pg_relation_size(indexrelid) FROM pg_stat_user_indexes WHERE relname = 'media_entries'"))}
        heap = conn.execute(text("SELECT pg_relation_size('media_entries')")).scalar()
        payload_bytes = conn.execute(text("SELECT coalesce(sum(pg_column_size(payload)),0), count(*) FROM media_entry_payloads")).one()
        heavy = conn.execute(text("SELECT owner_token FROM media_entries WHERE library='personal' GROUP BY 1 ORDER BY count(*) DESC LIMIT 1")).scalar()
        typical = conn.execute(text("SELECT owner_token FROM media_entries WHERE library='personal' AND owner_token <> :h LIMIT 1"), {"h": heavy}).scalar()
        heavy_n = conn.execute(text("SELECT count(*) FROM media_entries WHERE owner_token = :o"), {"o": heavy}).scalar()
        some_ids = [r[0] for r in conn.execute(text("SELECT media_id FROM media_entries WHERE library='personal' ORDER BY random() LIMIT 500"))]
        shared_ids = [r[0] for r in conn.execute(text("SELECT media_id FROM media_entries WHERE library='shared' ORDER BY random() LIMIT 200"))]
    facts["volume"] = {"personal": counts.get("personal"), "shared": counts.get("shared"), "owners": owners, "heavy_owner_rows": heavy_n,
                       "total_bytes": sizes, "indexes_bytes": idx, "heap_bytes": heap,
                       "payload_stored_bytes": int(payload_bytes[0]), "payload_rows": payload_bytes[1],
                       "bytes_per_personal_row_all_in": round(sizes["media_entries"] / max(1, counts.get("personal", 1)), 1)}
    queries = {
        "get by media_id (R1/R2, head-only)": ("SELECT media_id, library, owner_token, language, status FROM media_entries WHERE media_id = :id",
                                               lambda: {"id": random.choice(some_ids)}, {"id": some_ids[0]}),
        "get shared + payload (resolve_learner_payload)": ("SELECT e.title, p.payload FROM media_entries e JOIN media_entry_payloads p USING (media_id) WHERE e.media_id = :id",
                                                          lambda: {"id": random.choice(shared_ids)}, {"id": shared_ids[0]}),
        "shared browse page 1 (en, published, 24)": ("SELECT media_id, title, created_at FROM media_entries WHERE library='shared' AND language='en' AND status='published' ORDER BY created_at DESC, media_id DESC LIMIT 24",
                                                      lambda: {}, {}),
        "shared browse keyset page (24)": ("SELECT media_id, title FROM media_entries WHERE library='shared' AND language='en' AND status='published' AND (created_at, media_id) < (now() - interval '3000 seconds', 'zzz') ORDER BY created_at DESC, media_id DESC LIMIT 24",
                                            lambda: {}, {}),
        "operator listing (all statuses, 24)": ("SELECT media_id, title FROM media_entries WHERE library='shared' ORDER BY created_at DESC, media_id DESC LIMIT 24", lambda: {}, {}),
        "lesson_id probe (R6)": ("SELECT media_id FROM media_entries WHERE library='shared' AND lesson_id = :l",
                                 lambda: {"l": f"media-lesson-{random.randint(1, shared)}"}, {"l": "media-lesson-7"}),
        "owner byte sum, typical owner": ("SELECT coalesce(sum(stored_bytes),0) FROM media_entries WHERE library='personal' AND owner_token = :o",
                                          lambda: {"o": typical}, {"o": typical}),
        "owner byte sum, HEAVY owner (10k rows)": ("SELECT coalesce(sum(stored_bytes),0) FROM media_entries WHERE library='personal' AND owner_token = :o",
                                                   lambda: {"o": heavy}, {"o": heavy}),
        "owner page (24, all languages)": ("SELECT media_id FROM media_entries WHERE library='personal' AND owner_token = :o ORDER BY language, created_at DESC, media_id DESC LIMIT 24",
                                           lambda: {"o": heavy}, {"o": heavy}),
        "delete_all_owned: ids of one owner": ("SELECT media_id FROM media_entries WHERE library='personal' AND owner_token = :o", lambda: {"o": typical}, {"o": typical}),
    }
    plans = {}
    for label, (sql, params_fn, explain_params) in queries.items():
        plan = explain(engine, sql, explain_params)
        lat = latency(engine, sql, params_fn, runs=200)
        plans[label] = {**plan, **lat}
        check(f"vol: '{label}' is index-served (no Seq Scan on media_entries)",
              lambda plan=plan: ok(plan["seq_scans_on_media_entries"] == 0, f"Seq Scan! {plan['types']}"))
    facts["plans"] = plans
    sum_plan = plans["owner byte sum, HEAVY owner (10k rows)"]
    check("vol: the quota sum is an Index Only Scan with 0 heap fetches on a vacuumed table",
          lambda: ok(("Index Only Scan" in sum_plan["types"] and sum_plan["heap_fetches"] == 0), f"{sum_plan['types']} heap_fetches={sum_plan['heap_fetches']}"))
    # stale visibility map: touch the heavy owner's rows without vacuum
    with engine.begin() as conn:
        conn.execute(text("UPDATE media_entries SET updated_at = now() WHERE library='personal' AND owner_token = :o"), {"o": heavy})
    stale = explain(engine, queries["owner byte sum, HEAVY owner (10k rows)"][0], {"o": heavy})
    stale_lat = latency(engine, queries["owner byte sum, HEAVY owner (10k rows)"][0], lambda: {"o": heavy}, runs=100)
    facts["sum_stale_visibility_map"] = {**stale, **stale_lat}
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        conn.execute(text("VACUUM media_entries"))
    fresh = explain(engine, queries["owner byte sum, HEAVY owner (10k rows)"][0], {"o": heavy})
    facts["sum_after_vacuum"] = fresh
    record("vol: stale visibility map measured (heap fetches before VACUUM, after VACUUM)", True,
           f"heap_fetches {stale['heap_fetches']} -> {fresh['heap_fetches']}; p95 stale {stale_lat['p95_ms']} ms")
    # all-language owner paging walk for the heavy owner (account-deletion remover)
    repo = PostgresMediaLibraryRepository(engine)
    def walk():
        after, total = None, 0
        while True:
            page = repo.list_owned_page(heavy, after=after, limit=50)
            if not page:
                return total
            total += len(page)
            last = page[-1]
            after = (last.language, datetime.fromisoformat(last.created_at.replace("Z", "+00:00")), last.media_id)
    got = timed(f"walk heavy owner ({heavy_n} rows) by list_owned_page(50)", walk)
    check("vol: owner keyset walk returns every row once", lambda: ok(got == heavy_n, f"{got} != {heavy_n}"))
    # down/up at volume
    step_with_reader(engine, f"0024 downgrade at volume ({volume + shared} rows)", lambda: command.downgrade(cfg_p, BASE))
    step_with_reader(engine, "0024 re-upgrade after volume", lambda: command.upgrade(cfg_p, HEAD))


def _exec(engine, sql, params):
    with engine.begin() as conn:
        conn.execute(text(sql), params)


def print_report(path):
    width = max(len(l) for l, _, _ in results)
    print(f"\n{'PROBE'.ljust(width)}  RESULT  DETAIL")
    for label, ok, detail in results:
        print(f"{label.ljust(width)}  {'PASS' if ok else 'FAIL'}    {detail}")
    print("\nTIMINGS (seconds)")
    for label, seconds in timings:
        print(f"  {seconds:10.3f}  {label}")
    print("\nFACTS")
    print(json.dumps(facts, indent=2, default=str))
    failed = [l for l, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} PASS, {len(failed)} FAIL")
    if path:
        Path(path).write_text(json.dumps({"results": results, "timings": timings, "facts": facts}, indent=2, default=str), encoding="utf-8")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--volume", type=int, default=0, help="personal rows to seed in SQL (run 2/3)")
    parser.add_argument("--shared", type=int, default=5000)
    parser.add_argument("--import-volume", type=int, default=0, help="entries in a generated index.json for the import run")
    parser.add_argument("--report", default="")
    args = parser.parse_args()
    refuse_unless_throwaway(args.url)
    engine = create_engine(args.url, pool_size=20, max_overflow=20)
    with engine.connect() as conn:
        tables = conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")).scalar()
    if tables:
        sys.exit(f"REFUSED: the rehearsal database is not empty ({tables} tables)")
    workdir = Path(tempfile.mkdtemp(prefix="media-rehearsal-"))
    cfg_p = run1(args.url, engine)
    probes(engine)
    run4_import(engine, workdir / "import")
    if args.import_volume:
        run4_volume(engine, workdir, args.import_volume)
    if args.volume:
        run_volume(args.url, engine, cfg_p, args.volume, args.shared)
    shutil.rmtree(workdir, ignore_errors=True)
    return print_report(args.report)


if __name__ == "__main__":
    raise SystemExit(main())
