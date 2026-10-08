"""Rehearsal of the PROPOSED migration 20261008_0030 (grammar content store) on a throwaway PostgreSQL.

`docs/project/proposals/GRAMMAR_CONTENT_STORE.md` revision 3, sections 3, 4, 6 and 11. Run by hand against a database
given by URL; not part of CI; it refuses anything that is not clearly throwaway and empty (the guard of
`rehearse_learner_records_schema.py`). It applies the proposal from a temporary Alembic version location that holds
only this one file, on top of the real `migrations/versions/` chain, so the shared runtimes (which read
`migrations/versions/` alone) never see it.

    python scripts/rehearse_grammar_content_store.py "$REHEARSAL_URL" [--points 1000] [--progress 100000] [--report out.md]

The point bodies are SYNTHETIC (generated here, roughly 20 KB each, in the export-profile shape); no Grammar Lab corpus
is read or copied. The import, accept, attest and publish transactions are written here in SQL, as the proposal
specifies them, to exercise the schema; they are not the Store implementation, which waits for the review gate.

Steps (each a PASS/FAIL row; non-zero exit on any FAIL):
 1. chain: `migrations/versions/` alone has the single head 20261007_0029; with the proposal its single head is
    20261008_0030 and its parent is that head.
 2. 0029 + 1,000 users + 100,000 `grammar_progress` rows (R5 composite keys, point ids, quiz results), fingerprinted.
 3. upgrade to 0030 while every pre-existing table except `alembic_version` is held ACCESS EXCLUSIVE by another
    session, with `lock_timeout` set: the revision takes no lock on any existing table.
 4. shape: eight tables, two triggers, the partial unique indexes, no foreign key to a pre-existing table, nothing else
    in the schema changed; progress fingerprint unchanged.
 5. downgrade to 0029: the schema equals the pre-upgrade schema exactly; progress fingerprint unchanged. Upgrade again:
    the schema equals the first upgrade's.
 6. synthetic import of N points (two languages, merged/split/dropped R5 rows) in one transaction, timed; batch
    attestation after import (review N-4); accept; bulk publish in one transaction, timed.
 7. constraints: one published version per point; publish gate (accepted + cleared); projection while published;
    id/language agreement; R5 one-resolution (N-3) across batches; dropped/primary shape; package hash idempotency.
 8. immutability: the trigger rejects UPDATE of every content column and DELETE of a version, allows the review
    columns; review events are append-only.
 9. a failed publish (CHECK at the gate; an injected fault after tag rebuild and revision bump; a concurrent second
    publish of the same point) leaves versions, projection, tags, events and the catalogue revision unchanged.
10. read paths: EXPLAIN of the catalogue, point, by-error, R5 resolution and progress reads names the intended index.
11. catalogue revision / ETag read order: revision-first never labels older content with a newer revision (scripted
    interleavings and a concurrent stress); the reversed order is shown to produce that hazard.
12. `grammar_progress` intact after everything (count and digest), and a progress row survives archiving its point.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]

import sqlalchemy as sa  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from rehearse_learner_records_schema import refuse_unless_empty, refuse_unless_throwaway  # noqa: E402

VERSIONS = ROOT / "migrations" / "versions"
PROPOSAL = ROOT / "migrations" / "proposed" / "20261008_0030_grammar_content_store.py"
HEAD = "20261007_0029"
REV = "20261008_0030"
TABLES = (
    "grammar_import_batches", "grammar_functions", "grammar_points", "grammar_point_versions", "grammar_r5_map",
    "grammar_point_error_tags", "grammar_review_events", "grammar_catalog_state",
)
RESULTS: list[tuple[str, bool, str]] = []
TIMINGS: list[tuple[str, float]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)


def timed(label: str, function):
    start = time.monotonic()
    value = function()
    TIMINGS.append((label, round(time.monotonic() - start, 3)))
    return value


LAST_ERROR = [""]


def refused(engine, sql: str, params: dict | None = None) -> str:
    """Run one statement in its own transaction; the SQLSTATE it fails with, or '' if it succeeded (rolled back).
    The database's message is kept in LAST_ERROR, so a check can say WHICH guard refused."""
    LAST_ERROR[0] = ""
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            conn.execute(text(sql), params or {})
        except sa.exc.DBAPIError as error:
            tx.rollback()
            LAST_ERROR[0] = str(error.orig).splitlines()[0][:160]
            return getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None) or "error"
        tx.rollback()
    return ""


def refused_by_trigger(engine, sql: str, params: dict, words: str) -> bool:
    return refused(engine, sql, params) == "23514" and words in LAST_ERROR[0]


# --- Alembic, with the proposal in a location of its own ------------------------------------------------------------

def alembic_config(url: str, proposal_dir: Path | None) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    locations = [str(VERSIONS)] + ([str(proposal_dir)] if proposal_dir else [])
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("version_locations", __import__("os").pathsep.join(locations))
    return cfg


def current(engine) -> str | None:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


# --- Schema signature ------------------------------------------------------------------------------------------------

def signature(engine) -> dict[str, set]:
    queries = {
        "columns": "SELECT table_name, column_name, data_type, is_nullable, coalesce(column_default, '')"
                   " FROM information_schema.columns WHERE table_schema = 'public'",
        "constraints": "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) FROM pg_constraint"
                       " WHERE connamespace = 'public'::regnamespace",
        "indexes": "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'",
        "triggers": "SELECT tgrelid::regclass::text, tgname, pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal",
        "functions": "SELECT proname, pg_get_function_identity_arguments(oid) FROM pg_proc"
                     " WHERE pronamespace = 'public'::regnamespace",
    }
    with engine.connect() as conn:
        return {name: {tuple(row) for row in conn.execute(text(sql))} for name, sql in queries.items()}


def without_grammar(sig: dict[str, set]) -> dict[str, set]:
    def keep(row) -> bool:
        return not any(str(value).startswith(TABLES) or str(value).startswith("grammar_point_version_is")
                       or str(value).startswith("grammar_review_event_is") for value in row[:2])
    return {name: {row for row in rows if keep(row)} for name, rows in sig.items()}


# --- grammar_progress -------------------------------------------------------------------------------------------------

def seed_progress(engine, users: int, rows: int) -> None:
    per_user = max(1, rows // users)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
            " SELECT gen_random_uuid(), 'rehearsal-user-' || n, '', '', '', 'user', now()"
            " FROM generate_series(1, :n) AS n"), {"n": users})
        # A third R5 composite keys (`en:grammar:v2:<r5id>`), a third Grammar Lab point ids, a third with a quiz result.
        conn.execute(text(
            "INSERT INTO grammar_progress (id, user_id, language_code, lesson_id, completed_at,"
            " last_quiz_correct, last_quiz_total, last_quiz_at)"
            " SELECT gen_random_uuid(), u.id, CASE WHEN k % 5 = 0 THEN 'zh' ELSE 'en' END,"
            "   CASE WHEN k % 3 = 0 THEN (CASE WHEN k % 5 = 0 THEN 'zh' ELSE 'en' END) || ':grammar:v2:r5-lesson-' || k"
            "        ELSE (CASE WHEN k % 5 = 0 THEN 'zh' ELSE 'en' END) || '.rehearsal_point_' || k END,"
            "   now() - (k || ' minutes')::interval,"
            "   CASE WHEN k % 3 = 1 THEN k % 4 END, CASE WHEN k % 3 = 1 THEN 4 END,"
            "   CASE WHEN k % 3 = 1 THEN now() END"
            " FROM users u CROSS JOIN generate_series(1, :per) AS k WHERE u.user_key LIKE 'rehearsal-user-%'"),
            {"per": per_user})


def progress_fingerprint(engine) -> tuple[int, str]:
    with engine.connect() as conn:
        return tuple(conn.execute(text(
            "SELECT count(*), md5(coalesce(string_agg(id::text || '|' || user_id::text || '|' || language_code || '|'"
            " || lesson_id || '|' || completed_at::text || '|' || coalesce(last_quiz_correct::text, '-') || '|'"
            " || coalesce(last_quiz_total::text, '-') || '|' || coalesce(last_quiz_at::text, '-'), ',' ORDER BY id), ''))"
            " FROM grammar_progress")).one())


# --- Synthetic content, in the export-profile shape (never the corpus) ------------------------------------------------

def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def synthetic_point(point_id: str, lang: str, n: int, function: str, *, version: int = 1, marker: int = 0,
                    aliases: list[str] | None = None, split_of: list[str] | None = None) -> dict:
    level = {"framework": "cefr", "value": ["A1", "A2", "B1", "B2", "C1", "C2"][n % 6], "rank": n % 6 + 1} \
        if lang == "en" else {"framework": "hsk3", "value": str(n % 9 + 1), "rank": n % 9 + 1}
    text_vi = "Ví dụ có dấu tiếng Việt: hành động đã hoàn thành, ộ ữ ư. " * 3
    examples = [{
        "text": f"Rehearsal example {k} for {point_id}." if lang == "en" else f"我昨天买了第{k}本书。",
        "form": "affirmative",
        "spans": [{"start": 0, "end": 1, "role": "subject"}],
        "translation": {"vi": text_vi, "en": f"Example {k} translated."},
    } for k in range(48)]
    return {
        "id": point_id, "version": version, "status": "approved", "target_lang": lang, "function": function,
        "level": level, "prereqs": [], "contrasts": [], "error_tags": [f"tag_{n % 40}", f"tag_{(n + 7) % 40}"],
        "source_refs": {"egp": [f"egp-{n}"], **({"r5_split": split_of} if split_of else {})},
        "point_type": "form", "sequence": n, "aliases": aliases or [],
        "header": {"title": {"vi": f"Điểm {n}", "en": f"Point {n}"}, "native_title": f"Point {n} ({marker})",
                   "sub": {"vi": text_vi, "en": "Subtitle."}},
        "when_to_use": [{"vi": text_vi, "en": "When to use."} for _ in range(4)],
        "pattern": {"formula": [{"role": "subject", "text": "S"}, {"role": "verb", "text": "V"}]},
        "examples": examples, "compare": [],
        "common_mistakes": [{"wrong": "x", "right": "y", "error_tag": f"tag_{n % 40}",
                             "reason": {"vi": text_vi, "en": "Reason."}}],
        "quick_practice": [{"q": f"Question {k}", "options": ["a", "b", "c"], "answer": k % 3} for k in range(5)],
        "rehearsal_marker": marker,
    }


def build_package(points: int) -> dict:
    """Two languages (60% en / 40% zh), 24 functions, R5 rows of every disposition."""
    rng = random.Random(30)
    functions = [{"id": f"fn.rehearsal_{k}", "title": {"vi": f"Nhóm {k}", "en": f"Group {k}", "zh": f"组{k}"}}
                 for k in range(24)]
    langs = {"en": int(points * 0.6), "zh": points - int(points * 0.6)}
    out: dict[str, dict] = {}
    for lang, count in langs.items():
        bodies, r5 = [], []
        for n in range(count):
            pid = f"{lang}.rehearsal.point_{n:04d}"
            aliases, split_of = [], None
            if n % 25 == 0:  # merged: two R5 ids -> one point
                aliases = [f"r5-{lang}-m{n}-a", f"r5-{lang}-m{n}-b"]
                r5 += [{"r5_id": a, "point_id": pid, "disposition": "merged", "is_primary": True} for a in aliases]
            elif n % 25 == 1:  # split primary; the next point is its secondary
                aliases = [f"r5-{lang}-s{n}"]
                r5 += [{"r5_id": aliases[0], "point_id": pid, "disposition": "split_primary", "is_primary": True},
                       {"r5_id": aliases[0], "point_id": f"{lang}.rehearsal.point_{n + 1:04d}",
                        "disposition": "split_secondary", "is_primary": False}]
            elif n % 25 == 2:
                split_of = [f"r5-{lang}-s{n - 1}"]
            else:
                aliases = [f"r5-{lang}-r{n}"]
                r5.append({"r5_id": aliases[0], "point_id": pid, "disposition": "replaced", "is_primary": True})
            body = synthetic_point(pid, lang, n, functions[rng.randrange(len(functions))]["id"],
                                   aliases=aliases, split_of=split_of)
            bodies.append(body)
        r5 += [{"r5_id": f"r5-{lang}-dropped-{k}", "point_id": None, "disposition": "dropped", "is_primary": False}
               for k in range(max(1, count // 30))]
        out[lang] = {"bodies": bodies, "r5_map": r5}
    return {"functions": functions, "languages": out}


# --- The proposal's transactions, in SQL --------------------------------------------------------------------------------

def import_batch(conn, lang: str, functions: list[dict], bodies: list[dict], r5_map: list[dict], *,
                 package_hash: str, actor: str = "rehearsal-admin") -> uuid.UUID:
    now = datetime.now(UTC)
    batch_id = uuid.uuid4()
    entries = [{"id": b["id"], "version": b["version"], "content_hash": hashlib.sha256(canonical(b)).hexdigest()}
               for b in bodies]
    manifest = {"export_profile": "grammar-export-profile/1", "schema_version": "0.4", "language": lang,
                "points": entries, "r5_map": r5_map, "validator": {"passed": True}}
    conn.execute(text(
        "INSERT INTO grammar_import_batches (id, status, language_code, package_hash, export_profile,"
        " profile_schema_hash, schema_version, set_version, source_commit, exported_at, filename, new_count,"
        " manifest, imported_by, created_at) VALUES (:id, 'imported', :lang, :hash, 'grammar-export-profile/1',"
        " :psh, '0.4', :sv, :commit, :now, :fn, :count, CAST(:manifest AS json), :actor, :now)"),
        {"id": batch_id, "lang": lang, "hash": package_hash, "psh": "0" * 64, "sv": f"rehearsal.{lang}",
         "commit": "f" * 40, "now": now, "fn": f"{lang}.zip", "count": len(bodies), "manifest": json.dumps(manifest),
         "actor": actor})
    if functions:
        conn.execute(text(
            "INSERT INTO grammar_functions (id, title, batch_id, updated_at) VALUES (:id, CAST(:title AS json), :b, :now)"
            " ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, batch_id = EXCLUDED.batch_id,"
            " updated_at = EXCLUDED.updated_at"),
            [{"id": f["id"], "title": json.dumps(f["title"], ensure_ascii=False), "b": batch_id, "now": now}
             for f in functions])
    conn.execute(text(
        "INSERT INTO grammar_points (id, language_code, created_at, updated_at) VALUES (:id, :lang, :now, :now)"
        " ON CONFLICT (id) DO NOTHING"), [{"id": b["id"], "lang": lang, "now": now} for b in bodies])
    version_rows = [{
        "id": uuid.uuid4(), "point": b["id"], "version": b["version"], "content": canonical(b).decode(),
        "hash": hashlib.sha256(canonical(b)).hexdigest(), "prov": json.dumps({"reviewer": "rehearsal", "run_id": "r"}),
        "b": batch_id, "now": now,
    } for b in bodies]
    conn.execute(text(
        "INSERT INTO grammar_point_versions (id, point_id, version, content, content_hash, source_status, provenance,"
        " batch_id, imported_at) VALUES (:id, :point, :version, CAST(:content AS json), :hash, 'approved',"
        " CAST(:prov AS json), :b, :now)"), version_rows)
    if r5_map:
        conn.execute(text(  # a batch's rows for an R5 id replace every earlier row for that id (section 9.2)
            "DELETE FROM grammar_r5_map WHERE language_code = :lang AND r5_id = ANY(:ids)"),
            {"lang": lang, "ids": sorted({row["r5_id"] for row in r5_map})})
        conn.execute(text(
            "INSERT INTO grammar_r5_map (id, language_code, r5_id, point_id, disposition, is_primary, batch_id,"
            " created_at) VALUES (:id, :lang, :r5, :point, :disp, :primary, :b, :now)"),
            [{"id": uuid.uuid4(), "lang": lang, "r5": row["r5_id"], "point": row["point_id"],
              "disp": row["disposition"], "primary": row["is_primary"], "b": batch_id, "now": now} for row in r5_map])
    conn.execute(text(
        "INSERT INTO grammar_review_events (id, point_id, version_id, batch_id, actor, action, created_at)"
        " VALUES (:id, :point, :version, :b, :actor, 'imported', :now)"),
        [{"id": uuid.uuid4(), "point": row["point"], "version": row["id"], "b": batch_id, "actor": actor, "now": now}
         for row in version_rows])
    return batch_id


def attest_and_accept(conn, batch_id: uuid.UUID, actor: str = "rehearsal-admin") -> None:
    now = datetime.now(UTC)
    conn.execute(text(
        "UPDATE grammar_import_batches SET rights_basis = 'orena_original', rights_attestation = :t,"
        " rights_attested_by = :a, rights_attested_at = :now WHERE id = :b"),
        {"t": "Synthetic rehearsal content, written for this rehearsal.", "a": actor, "now": now, "b": batch_id})
    conn.execute(text(
        "UPDATE grammar_point_versions SET rights_status = 'cleared', review_status = 'accepted', reviewed_by = :a,"
        " reviewed_at = :now WHERE batch_id = :b AND review_status = 'imported'"), {"a": actor, "now": now, "b": batch_id})


def publish(conn, version_ids: list[uuid.UUID], actor: str = "rehearsal-admin", fault=None) -> None:
    """Section 6: lock the points, supersede, publish, project, rebuild tags, bump the revision, write events."""
    now = datetime.now(UTC)
    rows = conn.execute(text(
        "SELECT v.id, v.point_id, CAST(v.content AS text) AS content, p.language_code FROM grammar_point_versions v"
        " JOIN grammar_points p ON p.id = v.point_id WHERE v.id = ANY(:ids) ORDER BY v.point_id"),
        {"ids": version_ids}).all()
    points = [row.point_id for row in rows]
    conn.execute(text("SELECT id FROM grammar_points WHERE id = ANY(:p) ORDER BY id FOR UPDATE"), {"p": points})
    conn.execute(text(
        "UPDATE grammar_point_versions SET is_published = false, review_status = 'superseded'"
        " WHERE point_id = ANY(:p) AND is_published AND NOT (id = ANY(:ids))"), {"p": points, "ids": version_ids})
    conn.execute(text("UPDATE grammar_point_versions SET is_published = true WHERE id = ANY(:ids)"), {"ids": version_ids})
    projection, tags = [], []
    for row in rows:
        body = json.loads(row.content)
        projection.append({
            "id": row.point_id, "fn": body["function"], "fw": body["level"]["framework"], "lv": body["level"]["value"],
            "rank": body["level"]["rank"], "seq": body["sequence"], "pt": body["point_type"],
            "nt": body["header"]["native_title"], "now": now})
        mistakes = {m["error_tag"] for m in body.get("common_mistakes", [])}
        tags += [{"p": row.point_id, "t": tag, "m": tag in mistakes} for tag in body.get("error_tags", [])]
    conn.execute(text(
        "UPDATE grammar_points SET lifecycle = 'published', published_at = :now, updated_at = :now, function_id = :fn,"
        " level_framework = :fw, level_value = :lv, level_rank = :rank, sequence = :seq, point_type = :pt,"
        " native_title = :nt WHERE id = :id"), projection)
    conn.execute(text("DELETE FROM grammar_point_error_tags WHERE point_id = ANY(:p)"), {"p": points})
    if tags:
        conn.execute(text("INSERT INTO grammar_point_error_tags (point_id, error_tag, has_mistake) VALUES (:p, :t, :m)"),
                     tags)
    for lang in sorted({row.language_code for row in rows}):
        conn.execute(text(
            "INSERT INTO grammar_catalog_state (language_code, revision, updated_at) VALUES (:l, 1, :now)"
            " ON CONFLICT (language_code) DO UPDATE SET revision = grammar_catalog_state.revision + 1,"
            " updated_at = EXCLUDED.updated_at"), {"l": lang, "now": now})
    if fault:
        fault()
    conn.execute(text(
        "INSERT INTO grammar_review_events (id, point_id, version_id, actor, action, created_at)"
        " VALUES (:id, :p, :v, :a, 'published', :now)"),
        [{"id": uuid.uuid4(), "p": row.point_id, "v": row.id, "a": actor, "now": now} for row in rows])


def revision_of(conn, lang: str) -> int:
    return conn.execute(text("SELECT coalesce((SELECT revision FROM grammar_catalog_state WHERE language_code = :l), 0)"),
                        {"l": lang}).scalar()


def state_of(engine, point_id: str) -> tuple:
    with engine.connect() as conn:
        return (
            tuple(conn.execute(text(
                "SELECT id::text, review_status, is_published, rights_status FROM grammar_point_versions"
                " WHERE point_id = :p ORDER BY version"), {"p": point_id}).all()),
            tuple(conn.execute(text(
                "SELECT lifecycle, native_title, published_at FROM grammar_points WHERE id = :p"), {"p": point_id}).one()),
            tuple(conn.execute(text(
                "SELECT error_tag, has_mistake FROM grammar_point_error_tags WHERE point_id = :p ORDER BY error_tag"),
                {"p": point_id}).all()),
            conn.execute(text("SELECT count(*) FROM grammar_review_events WHERE point_id = :p"), {"p": point_id}).scalar(),
            tuple(conn.execute(text("SELECT language_code, revision FROM grammar_catalog_state ORDER BY 1")).all()),
        )


def new_version(engine, point_id: str, lang: str, version: int, marker: int, *, cleared: bool) -> uuid.UUID:
    body = synthetic_point(point_id, lang, 7, "fn.rehearsal_0", version=version, marker=marker)
    with engine.begin() as conn:
        batch = import_batch(conn, lang, [], [body], [], package_hash=hashlib.sha256(
            f"{point_id}:{version}:{marker}".encode()).hexdigest())
        conn.execute(text(
            "UPDATE grammar_point_versions SET review_status = 'accepted', rights_status = :r WHERE batch_id = :b"),
            {"r": "cleared" if cleared else "unknown", "b": batch})
        return conn.execute(text("SELECT id FROM grammar_point_versions WHERE batch_id = :b"), {"b": batch}).scalar()


def plan_indexes(engine, sql: str, params: dict, *, force: bool = False) -> tuple[set[str], str]:
    with engine.connect() as conn:
        tx = conn.begin()
        if force:
            conn.execute(text("SET LOCAL enable_seqscan = off"))
        plan = conn.execute(text("EXPLAIN (ANALYZE, FORMAT JSON) " + sql), params).scalar()
        tx.rollback()
    plan = plan if isinstance(plan, list) else json.loads(plan)
    found: set[str] = set()

    def walk(node):
        if "Index Name" in node:
            found.add(node["Index Name"])
        for child in node.get("Plans", []):
            walk(child)
    walk(plan[0]["Plan"])
    return found, f"{plan[0]['Plan']['Node Type']} {plan[0].get('Execution Time', 0):.2f} ms"


# --- Main --------------------------------------------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url")
    parser.add_argument("--points", type=int, default=1000)
    parser.add_argument("--progress", type=int, default=100_000)
    parser.add_argument("--users", type=int, default=1000)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    refuse_unless_throwaway(args.url)
    engine = create_engine(args.url, future=True, pool_size=16, max_overflow=16)
    refuse_unless_empty(engine)
    with engine.connect() as conn:
        server = conn.execute(text("SHOW server_version")).scalar()
    print("server:", server)
    proposal_dir = Path(tempfile.mkdtemp(prefix="grammar-store-proposal-"))
    shutil.copy(PROPOSAL, proposal_dir / PROPOSAL.name)
    try:
        return run(args, engine, proposal_dir, server)
    finally:
        shutil.rmtree(proposal_dir, ignore_errors=True)


def run(args, engine, proposal_dir: Path, server: str) -> int:
    cfg_v, cfg_p = alembic_config(args.url, None), alembic_config(args.url, proposal_dir)

    # 1. chain -------------------------------------------------------------------------------------------------------
    heads_v = ScriptDirectory.from_config(cfg_v).get_heads()
    script_p = ScriptDirectory.from_config(cfg_p)
    heads_p = script_p.get_heads()
    check("1 versions/ alone: single head 20261007_0029", heads_v == [HEAD], str(heads_v))
    check("1 with the proposal: single head 20261008_0030, parented on the versions head",
          heads_p == [REV] and script_p.get_revision(REV).down_revision == heads_v[0], f"{heads_p}")

    # 2. 0029 + progress ----------------------------------------------------------------------------------------------
    timed("upgrade empty -> 0029 (real chain)", lambda: command.upgrade(cfg_v, HEAD))
    check("2 chain applied to 20261007_0029", current(engine) == HEAD, str(current(engine)))
    timed(f"seed {args.users} users + {args.progress} grammar_progress rows",
          lambda: seed_progress(engine, args.users, args.progress))
    progress0 = progress_fingerprint(engine)
    check(f"2 {args.progress} grammar_progress rows seeded", progress0[0] == args.progress, str(progress0[0]))
    sig_0029 = signature(engine)

    # 3. upgrade with every existing table locked by another session ----------------------------------------------------
    with engine.connect() as conn:
        existing = [r[0] for r in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"))]
    holder = engine.connect()
    holder_tx = holder.begin()
    holder.execute(text("LOCK TABLE " + ", ".join(f'"{t}"' for t in existing) + " IN ACCESS EXCLUSIVE MODE"))
    url = make_url(args.url).update_query_dict({"options": "-c lock_timeout=5000"})
    cfg_locked = alembic_config(url.render_as_string(hide_password=False), proposal_dir)
    error = ""
    try:
        timed("upgrade 0029 -> 0030 (all existing tables locked elsewhere)", lambda: command.upgrade(cfg_locked, REV))
    except Exception as exc:  # noqa: BLE001 - reported
        error = f"{type(exc).__name__}: {str(exc)[:160]}"
    holder_tx.rollback()
    holder.close()
    check(f"3 upgrade to 0030 completes while all {len(existing)} existing tables are ACCESS EXCLUSIVE locked"
          " elsewhere (lock_timeout 5s): no lock on any existing table", not error and current(engine) == REV, error)

    # 4. shape ------------------------------------------------------------------------------------------------------------
    sig_0030 = signature(engine)
    inspector = sa.inspect(engine)
    names = set(inspector.get_table_names())
    check("4 the eight grammar tables exist", set(TABLES) <= names, str(sorted(set(TABLES) - names)))
    foreign = sorted({(t, fk["referred_table"]) for t in TABLES for fk in inspector.get_foreign_keys(t)
                      if fk["referred_table"] not in TABLES})
    check("4 no foreign key from a grammar table to a pre-existing table", not foreign, str(foreign))
    order = {t: i for i, t in enumerate(TABLES)}
    backwards = [(t, fk["referred_table"]) for t in TABLES for fk in inspector.get_foreign_keys(t)
                 if order[fk["referred_table"]] >= order[t]]
    check("4 foreign keys are cycle-free (each points to an earlier table)", not backwards, str(backwards))
    check("4 nothing outside the grammar tables changed", without_grammar(sig_0030) == sig_0029,
          str({k: len(sig_0029[k] ^ without_grammar(sig_0030)[k]) for k in sig_0029}))
    triggers = {row[1] for row in sig_0030["triggers"]}
    check("4 PostgreSQL triggers installed", {"grammar_point_version_immutable", "grammar_review_event_append_only"}
          <= triggers, str(sorted(triggers)))
    partial = {row[1]: row[2] for row in sig_0030["indexes"] if " WHERE " in row[2] and row[0] in TABLES}
    check("4 partial unique indexes: one published version, one resolution per R5 id, one imported batch per hash",
          {"uq_grammar_point_versions_published", "uq_grammar_r5_map_resolution", "uq_grammar_import_batches_package"}
          <= set(partial), str(sorted(partial)))
    check("4 grammar_progress fingerprint unchanged by the upgrade", progress_fingerprint(engine) == progress0)

    # 5. down / up -------------------------------------------------------------------------------------------------------
    timed("downgrade 0030 -> 0029", lambda: command.downgrade(cfg_p, HEAD))
    check("5 downgrade: at 0029, schema identical to before the upgrade",
          current(engine) == HEAD and signature(engine) == sig_0029, str(current(engine)))
    check("5 downgrade: grammar_progress fingerprint unchanged", progress_fingerprint(engine) == progress0)
    timed("upgrade 0029 -> 0030 again", lambda: command.upgrade(cfg_p, REV))
    check("5 upgrade again: schema identical to the first upgrade",
          current(engine) == REV and signature(engine) == sig_0030, str(current(engine)))

    # 6. synthetic import, attestation, accept, bulk publish -------------------------------------------------------------
    package = build_package(args.points)
    batches = {}
    size = 0
    for lang, data in package["languages"].items():
        size += sum(len(canonical(b)) for b in data["bodies"])

        def do_import(lang=lang, data=data):
            with engine.begin() as conn:
                return import_batch(conn, lang, package["functions"], data["bodies"], data["r5_map"],
                                    package_hash=hashlib.sha256(f"pkg-{lang}".encode()).hexdigest())
        batches[lang] = timed(f"import {len(data['bodies'])} {lang} points in one transaction", do_import)
    with engine.connect() as conn:
        counts = conn.execute(text(
            "SELECT (SELECT count(*) FROM grammar_points), (SELECT count(*) FROM grammar_point_versions),"
            " (SELECT count(*) FROM grammar_r5_map), (SELECT count(*) FROM grammar_points WHERE lifecycle <> 'unpublished'),"
            " (SELECT count(*) FROM grammar_point_versions WHERE rights_status <> 'unknown')")).one()
    check(f"6 synthetic import: {args.points} points, ~{size // args.points // 1024} KB each, all unpublished and"
          " rights unknown", counts[0] == args.points and counts[1] == args.points and counts[3] == 0 and counts[4] == 0,
          f"points={counts[0]} versions={counts[1]} r5_rows={counts[2]}")
    for batch in batches.values():
        with engine.begin() as conn:
            attest_and_accept(conn, batch)
    with engine.connect() as conn:
        ids = [r[0] for r in conn.execute(text("SELECT id FROM grammar_point_versions"))]

    def bulk():
        with engine.begin() as conn:
            publish(conn, ids)
    timed(f"bulk publish {len(ids)} points in one transaction", bulk)
    with engine.connect() as conn:
        pub = conn.execute(text(
            "SELECT count(*) FILTER (WHERE lifecycle = 'published'), (SELECT count(*) FROM grammar_point_versions"
            " WHERE is_published), (SELECT count(*) FROM grammar_point_error_tags) FROM grammar_points")).one()
        revs = dict(conn.execute(text("SELECT language_code, revision FROM grammar_catalog_state")).all())
    check("6 bulk publish: every point published with one version, tags projected, one revision bump per language",
          pub[0] == args.points and pub[1] == args.points and pub[2] > 0 and revs == {"en": 1, "zh": 1},
          f"published={pub[0]} tags={pub[2]} revisions={revs}")

    # 7. constraints -----------------------------------------------------------------------------------------------------
    p0 = "en.rehearsal.point_0003"
    with engine.connect() as conn:
        v0 = conn.execute(text("SELECT id FROM grammar_point_versions WHERE point_id = :p"), {"p": p0}).scalar()
        b_en = batches["en"]
    v_extra = new_version(engine, p0, "en", 2, 99, cleared=True)
    check("7 a second published version of one point is refused (unique)",
          refused(engine, "UPDATE grammar_point_versions SET is_published = true WHERE id = :v", {"v": v_extra}) == "23505")
    v_unknown = new_version(engine, p0, "en", 3, 98, cleared=False)
    check("7 publishing a version whose rights are not cleared is refused (CHECK)", refused(
        engine, "UPDATE grammar_point_versions SET is_published = true WHERE id = :v", {"v": v_unknown}) == "23514")
    check("7 restricting the rights of the published version is refused until it is unpublished (CHECK)", refused(
        engine, "UPDATE grammar_point_versions SET rights_status = 'restricted' WHERE id = :v", {"v": v0}) == "23514")
    check("7 a published point without its projection is refused (CHECK)", refused(
        engine, "UPDATE grammar_points SET native_title = NULL WHERE id = :p", {"p": p0}) == "23514")
    check("7 a point id whose prefix disagrees with its language is refused (CHECK)", refused(
        engine, "INSERT INTO grammar_points (id, language_code, created_at, updated_at) VALUES"
        " ('zh.wrong_language', 'en', now(), now())") == "23514")
    r5_sql = ("INSERT INTO grammar_r5_map (id, language_code, r5_id, point_id, disposition, is_primary, batch_id,"
              " created_at) VALUES (gen_random_uuid(), 'en', :r5, :p, :d, :pr, :b, now())")
    check("7 a second batch cannot leave an R5 id both mapped and dropped (N-3, unique)", refused(
        engine, r5_sql, {"r5": "r5-en-r3", "p": None, "d": "dropped", "pr": False, "b": b_en}) == "23505")
    check("7 a second primary for one R5 id is refused (unique)", refused(
        engine, r5_sql, {"r5": "r5-en-r3", "p": "en.rehearsal.point_0004", "d": "replaced", "pr": True, "b": b_en}) == "23505")
    check("7 a dropped row cannot name a point (CHECK)", refused(
        engine, r5_sql, {"r5": "r5-new", "p": p0, "d": "dropped", "pr": False, "b": b_en}) == "23514")
    check("7 a split secondary cannot be primary (CHECK)", refused(
        engine, r5_sql, {"r5": "r5-new", "p": p0, "d": "split_secondary", "pr": True, "b": b_en}) == "23514")
    batch_sql = ("INSERT INTO grammar_import_batches (id, status, language_code, package_hash, export_profile,"
                 " profile_schema_hash, schema_version, set_version, source_commit, exported_at, manifest, imported_by,"
                 " created_at) VALUES (gen_random_uuid(), :s, 'en', :h, 'grammar-export-profile/1', :z, '0.4', 'x', 'y',"
                 " now(), CAST('{}' AS json), 'a', now())")
    pkg_en = hashlib.sha256(b"pkg-en").hexdigest()
    check("7 the same package hash cannot be imported twice (partial unique)",
          refused(engine, batch_sql, {"s": "imported", "h": pkg_en, "z": "0" * 64}) == "23505")
    check("7 a rejected receipt with that hash is allowed (a re-upload of a rejected file is a fresh attempt)",
          refused(engine, batch_sql, {"s": "rejected", "h": pkg_en, "z": "0" * 64}) == "")
    check("7 a batch attestation must be complete (CHECK)", refused(
        engine, "UPDATE grammar_import_batches SET rights_attestation = NULL WHERE id = :b", {"b": b_en}) == "23514")

    # 8. immutability --------------------------------------------------------------------------------------------------
    for column, value in (("content", "CAST('{\"id\": \"changed\"}' AS json)"), ("content_hash", "repeat('a', 64)"),
                          ("version", "version + 100"), ("point_id", "'en.rehearsal.point_0004'"),
                          ("provenance", "CAST('{}' AS json)"), ("source_status", "'approved '"),
                          ("batch_id", ":other"), ("imported_at", "imported_at + interval '1 day'")):
        params = {"v": v0, "other": batches["zh"]}
        check(f"8 trigger rejects UPDATE of {column}", refused_by_trigger(
            engine, f"UPDATE grammar_point_versions SET {column} = {value} WHERE id = :v", params,
            "is immutable content: import a new version"), LAST_ERROR[0])
    check("8 trigger rejects DELETE of a version", refused_by_trigger(
        engine, "DELETE FROM grammar_point_versions WHERE id = :v", {"v": v_unknown}, "is never deleted"),
        LAST_ERROR[0])
    check("8 trigger allows the review columns (reviewed_by, reviewed_at, review_note)", refused(
        engine, "UPDATE grammar_point_versions SET reviewed_by = 'x', reviewed_at = now(), review_note = 'n'"
        " WHERE id = :v", {"v": v0}) == "")
    check("8 a rewrite of content with identical bytes is allowed (no-op)", refused(
        engine, "UPDATE grammar_point_versions SET content = content WHERE id = :v", {"v": v0}) == "")
    check("8 review events are append-only (UPDATE refused)", refused_by_trigger(
        engine, "UPDATE grammar_review_events SET reason = 'x' WHERE point_id = :p", {"p": p0}, "append-only"))
    check("8 review events are append-only (DELETE refused)", refused_by_trigger(
        engine, "DELETE FROM grammar_review_events WHERE point_id = :p", {"p": p0}, "append-only"))

    # 9. failed publish leaves everything unchanged ---------------------------------------------------------------------
    before = state_of(engine, p0)

    def attempt(version_ids, fault=None) -> str:
        try:
            with engine.begin() as conn:
                publish(conn, version_ids, fault=fault)
        except Exception as exc:  # noqa: BLE001 - the failure is the point
            return type(exc).__name__
        return ""
    failed = attempt([v_unknown])
    check("9 publish of an uncleared version fails at the gate after superseding; nothing changed",
          bool(failed) and state_of(engine, p0) == before, failed)

    def boom():
        raise RuntimeError("injected fault after tag rebuild and revision bump")
    failed = attempt([v_extra], fault=boom)
    check("9 an injected fault after tag rebuild and revision bump rolls everything back", bool(failed)
          and state_of(engine, p0) == before, failed)
    v_racer = new_version(engine, p0, "en", 4, 97, cleared=True)
    before = state_of(engine, p0)
    gate = threading.Barrier(2)
    outcome: dict[str, str] = {}

    def racer(name, vid):
        conn = engine.connect()
        tx = conn.begin()
        try:
            gate.wait(10)
            publish(conn, [vid])
            time.sleep(0.5 if name == "first" else 0)
            tx.commit()
            outcome[name] = "committed"
        except Exception as exc:  # noqa: BLE001
            tx.rollback()
            outcome[name] = type(exc).__name__
        finally:
            conn.close()
    threads = [threading.Thread(target=racer, args=("first", v_extra)), threading.Thread(target=racer, args=("second", v_racer))]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    after = state_of(engine, p0)
    with engine.connect() as conn:
        published_now = conn.execute(text(
            "SELECT count(*) FROM grammar_point_versions WHERE point_id = :p AND is_published"), {"p": p0}).scalar()
    rev_before = dict(before[4])["en"]
    rev_after = dict(after[4])["en"]
    committed = sorted(name for name, value in outcome.items() if value == "committed")
    check("9 two concurrent publishes of one point: the point lock serializes them; one published version, one bump"
          " per committed publish", published_now == 1 and rev_after - rev_before == len(committed) and committed,
          f"outcome={outcome} revision {rev_before}->{rev_after}")

    # 10. read paths ---------------------------------------------------------------------------------------------------
    with engine.begin() as conn:
        conn.execute(text("ANALYZE"))
        user_id, lesson = conn.execute(text("SELECT user_id, lesson_id FROM grammar_progress LIMIT 1")).one()
    reads = (
        ("catalogue (GET /points)", "SELECT id, function_id, level_rank, sequence, native_title FROM grammar_points"
         " WHERE language_code = 'en' AND lifecycle = 'published' ORDER BY level_rank, function_id, sequence",
         {}, "ix_grammar_points_catalog"),
        ("point (GET /points/{id})", "SELECT content, content_hash FROM grammar_point_versions WHERE point_id = :p"
         " AND is_published", {"p": p0}, "uq_grammar_point_versions_published"),
        ("by-error (GET /by-error)", "SELECT p.id, t.has_mistake FROM grammar_point_error_tags t JOIN grammar_points p"
         " ON p.id = t.point_id WHERE t.error_tag = 'tag_3' AND p.language_code = 'en' AND p.lifecycle = 'published'",
         {}, "ix_grammar_point_error_tags_tag"),
        ("R5 resolution", "SELECT point_id, disposition FROM grammar_r5_map WHERE language_code = 'en'"
         " AND r5_id = 'r5-en-r3' AND (is_primary OR point_id IS NULL)", {}, "uq_grammar_r5_map_resolution"),
        ("merged completion (R5 ids of a point)", "SELECT r5_id FROM grammar_r5_map WHERE point_id = :p AND is_primary",
         {"p": "en.rehearsal.point_0000"}, "ix_grammar_r5_map_point"),
        ("progress (grammar_progress)", "SELECT lesson_id, completed_at FROM grammar_progress WHERE user_id = :u"
         " AND language_code = 'en' AND lesson_id = ANY(:ids)", {"u": user_id, "ids": [lesson, "en:grammar:v2:x"]},
         "uq_grammar_progress_scope"),
    )
    for label, sql, params, index in reads:
        found, summary = plan_indexes(engine, sql, params)
        forced, _ = plan_indexes(engine, sql, params, force=True)
        check(f"10 read path {label}: {index} {'chosen' if index in found else 'usable (planner prefers a scan at this size)'}",
              index in found or index in forced, f"default plan: {summary}; indexes={sorted(found) or '-'}")

    # 11. ETag read order -------------------------------------------------------------------------------------------
    race_point = "en.rehearsal.point_0005"

    def published_marker(conn) -> int:
        return conn.execute(text(
            "SELECT CAST(content ->> 'rehearsal_marker' AS integer) FROM grammar_point_versions"
            " WHERE point_id = :p AND is_published"), {"p": race_point}).scalar()

    def publish_marker(marker: int) -> int:
        vid = new_version(engine, race_point, "en", 100 + marker, marker, cleared=True)
        with engine.begin() as conn:
            publish(conn, [vid])
            return revision_of(conn, "en")

    # Make the marker equal the revision it was published under, so "content older than its label" is marker < label.
    with engine.connect() as conn:
        base = revision_of(conn, "en")
    publish_marker(base + 1)
    reader = engine.connect()
    reader.execute(text("SELECT 1"))
    label = revision_of(reader, "en")                      # revision FIRST ...
    publish_marker(label + 1)                               # ... a publish commits in between ...
    seen = published_marker(reader)                         # ... then the content
    reader.rollback()
    check("11 revision-first: a publish between the reads yields NEWER content under the older label (harmless:"
          " the next request sees a new revision and refetches)", seen == label + 1, f"label={label} content={seen}")
    content_early = published_marker(reader)                # reversed order: content first ...
    with engine.connect() as conn:
        latest = revision_of(conn, "en")
    publish_marker(latest + 1)                              # ... a publish commits in between ...
    newer_label = revision_of(reader, "en")                 # ... then the revision
    reader.rollback()
    check("11 reversed order (content, then revision) demonstrably labels OLDER content with the NEWER revision (the"
          " 304-forever hazard the proposal's order avoids)", content_early < newer_label,
          f"content={content_early} label={newer_label}")
    rr = engine.connect().execution_options(isolation_level="REPEATABLE READ")
    tx = rr.begin()
    rr_label = revision_of(rr, "en")
    publish_marker(rr_label + 1)
    rr_seen = published_marker(rr)
    tx.rollback()
    rr.close()
    check("11 alternative: both reads in one REPEATABLE READ transaction are consistent", rr_seen == rr_label,
          f"label={rr_label} content={rr_seen}")
    reader.close()

    stop = threading.Event()
    violations: list[tuple[int, int]] = []
    reversed_violations: list[tuple[int, int]] = []
    reads_done = [0]
    publishes_done = [0]

    def publisher():
        while not stop.is_set():
            with engine.connect() as conn:
                nxt = revision_of(conn, "en") + 1
            publish_marker(nxt)
            publishes_done[0] += 1

    def correct_reader():
        while not stop.is_set():
            with engine.connect() as conn:
                lab = revision_of(conn, "en")
                mark = published_marker(conn)
            reads_done[0] += 1
            if mark < lab:
                violations.append((lab, mark))

    def reversed_reader():
        while not stop.is_set():
            with engine.connect() as conn:
                mark = published_marker(conn)
                lab = revision_of(conn, "en")
            if mark < lab:
                reversed_violations.append((lab, mark))
    workers = [threading.Thread(target=publisher)] + [threading.Thread(target=correct_reader) for _ in range(4)] + \
              [threading.Thread(target=reversed_reader) for _ in range(2)]
    [w.start() for w in workers]
    time.sleep(8)
    stop.set()
    [w.join(30) for w in workers]
    check("11 concurrent stress: revision-first reads never label older content with a newer revision",
          not violations and reads_done[0] > 0 and publishes_done[0] > 0,
          f"reads={reads_done[0]} publishes={publishes_done[0]} violations={len(violations)};"
          f" reversed-order violations observed={len(reversed_violations)} (informational)")

    # 12. learner progress -----------------------------------------------------------------------------------------------
    check("12 grammar_progress: count and digest unchanged after import, publish, failures and races",
          progress_fingerprint(engine) == progress0, f"rows={progress0[0]}")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO grammar_progress (id, user_id, language_code, lesson_id, completed_at) VALUES"
            " (gen_random_uuid(), :u, 'en', :p, now())"), {"u": user_id, "p": race_point})
        conn.execute(text(
            "UPDATE grammar_point_versions SET is_published = false WHERE point_id = :p AND is_published"),
            {"p": race_point})
        conn.execute(text(
            "UPDATE grammar_points SET lifecycle = 'archived', unpublished_at = now() WHERE id = :p"), {"p": race_point})
        conn.execute(text("DELETE FROM grammar_point_error_tags WHERE point_id = :p"), {"p": race_point})
    with engine.connect() as conn:
        kept = conn.execute(text("SELECT count(*) FROM grammar_progress WHERE lesson_id = :p"), {"p": race_point}).scalar()
    check("12 a learner's row under a point id survives archiving that point (no foreign key, no cascade)", kept == 1)
    check("12 nothing applied outside this database: versions/ has no 0030 and its head stays 20261007_0029",
          not list(VERSIONS.glob("*_0030_*")) and ScriptDirectory.from_config(cfg_v).get_heads() == [HEAD])

    # Final down: the rehearsal database returns to 0029 with progress intact.
    timed("final downgrade 0030 -> 0029 (with content loaded)", lambda: command.downgrade(cfg_p, HEAD))
    check("12 final downgrade with content loaded: grammar tables gone, progress intact",
          not (set(TABLES) & set(sa.inspect(engine).get_table_names()))
          and progress_fingerprint(engine)[0] == progress0[0] + 1)
    return report(args, server)


def report(args, server: str) -> int:
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(failed)} PASS, {len(failed)} FAIL")
    for label, seconds in TIMINGS:
        print(f"  {seconds:8.3f} s  {label}")
    if args.report:
        lines = [f"PostgreSQL {server}; points={args.points}; grammar_progress rows={args.progress};"
                 f" {len(RESULTS) - len(failed)} PASS, {len(failed)} FAIL", "", "| # | Check | Result | Detail |",
                 "| --- | --- | --- | --- |"]
        lines += [f"| {i} | {label} | {'PASS' if ok else 'FAIL'} | {detail.replace('|', '/')} |"
                  for i, (label, ok, detail) in enumerate(RESULTS, 1)]
        lines += ["", "| Step | Seconds |", "| --- | --- |"] + [f"| {label} | {seconds} |" for label, seconds in TIMINGS]
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
