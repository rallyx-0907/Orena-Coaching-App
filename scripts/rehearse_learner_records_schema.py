"""Rehearsal of the D4 learner-records migrations (0017-0023) on a throwaway PostgreSQL.

`docs/project/proposals/LEARNER_RECORDS_D4.md` (revision 3), D-104, D-102 point 7 and ORENA_ACCOUNT_DATA_ARCHITECTURE
section 6 step 3 ("SQLite tests alone are insufficient"). Kept in the repository so a reviewer can re-run it. It is not
part of CI and touches no runtime: it talks only to a database it is given by URL, and only if that database is clearly
throwaway and empty.

    docker run -d --name orena-d4-rehearsal -e POSTGRES_PASSWORD=rehearsal -e POSTGRES_DB=orena_d4_rehearsal \
        -p 55434:5432 postgres:17-alpine
    # in the application image (alembic, sqlalchemy and psycopg installed), repository mounted:
    python scripts/rehearse_learner_records_schema.py \
        postgresql+psycopg://postgres:rehearsal@host.docker.internal:55434/orena_d4_rehearsal
    docker rm -f orena-d4-rehearsal

What it does, in order (each line is a PASS or FAIL row; the exit code is non-zero on any FAIL):

1. Refuses a URL that is not clearly throwaway (see `refuse_unless_throwaway`) or a database that is not empty.
2. Builds the chain to 20260924_0016 from `migrations/versions/` only, and seeds rows that exist BEFORE the new columns.
3. Adds `migrations/proposed/` to `version_locations` and upgrades to head (20260930_0023, a single head).
4. Probes every new column, table, constraint, index and trigger: type, nullability, default, the value old rows read,
   the conditional update on `users.settings_updated_at`, the `essay_review_history` unique key, foreign-key cascades and
   immutability trigger, the `library_items` place columns and partial index, the `grammar_progress` quiz check.
5. Probes `lock_timeout`: while another connection holds a lock on `users`, a downgrade from head and an upgrade from
   0016 must each fail within a few seconds with SQLSTATE 55P03 and leave nothing half-applied.
6. Runs up -> down to 20260924_0016 -> up again, and asserts the downgrade removed everything it added while old rows
   survive, and that the schema after the second upgrade equals the schema after the first.
7. Races two writers on the `essay_review_history` unique key: one row, one refusal.

Also (delta review of revision 3):
- **Revisions are applied one per invocation** (`command.upgrade(cfg, <revision>)`), as the operator runbook does
  (`bootstrap_runtime_schema.py --upgrade --from <rev> --to <rev>`): the chain runs in one transaction, so a single run
  to head would keep 0018's lock on `users` through 0022's index build. Each invocation is timed; the timing table is
  printed with the results.
- `--volume N` seeds N rows into `users`, `user_language_profiles`, `library_items`, `grammar_progress`, `listening_progress`
  and `essays` (in SQL, before the migrations) so the lock-hold times are those of a table of that size. Use it for the
  maintenance-window measurement; without it the times only prove the shape.
- The schema after the downgrade is compared with the schema captured at 0016 (all public tables), not only with the
  schema after the first upgrade.
- Old-code inserts (naming none of the new columns) are probed for `users`, `user_language_profiles` and
  `listening_progress`.
- The `library_items` place write is probed with the conditional-upsert semantics of the proposal (I4): coalescing
  within 30 s unless a boundary, `version` and `updated_at` untouched, a concurrent pin PATCH unaffected.

Usage: `rehearse_learner_records_schema.py <URL> [--volume N]`.

The ORM models are intentionally unchanged until the human authorizes the migrations, so there is no ORM-parity step
here; the implementation adds it (`tests/test_reading_evidence_schema_parity.py` pattern) with the model changes.
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)  # alembic.ini has `prepend_sys_path = .`
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402

BASE = "20260924_0016"
HEAD = "20260930_0023"
NEW_REVISIONS = [
    "20260930_0017", "20260930_0018", "20260930_0019", "20260930_0020",
    "20260930_0021", "20260930_0022", "20260930_0023",
]
VERSIONS = ROOT / "migrations" / "versions"
PROPOSED = ROOT / "migrations" / "proposed"

# Everything the seven revisions add: (table, column). The tables they create are listed separately.
NEW_COLUMNS = [
    ("user_language_profiles", "declared_level"),
    ("users", "learning_language"), ("users", "interface_language"),
    ("users", "weekly_goal_days"), ("users", "settings_updated_at"),
    ("user_language_profiles", "review_new_per_day"), ("user_language_profiles", "review_limit_per_day"),
    ("user_language_profiles", "review_modes"),
    ("listening_progress", "score_source"),
    ("library_items", "place"), ("library_items", "place_at"),
    ("grammar_progress", "last_quiz_correct"), ("grammar_progress", "last_quiz_total"),
    ("grammar_progress", "last_quiz_at"),
]
NEW_TABLES = ["essay_review_history"]
NEW_INDEXES = ["ix_essay_review_history_essay", "ix_library_items_place"]

# ---------------------------------------------------------------------------------------------------------------------
# The guard: this script creates and drops schema, so it must never be pointed at a real runtime.
# ---------------------------------------------------------------------------------------------------------------------
THROWAWAY_NAME = re.compile(r"(rehears|throwaway|scratch)", re.IGNORECASE)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "orena-d4-rehearsal"}
RUNTIME_DATABASES = {"becoming", "postgres", "orena", "ai_writing_coach"}


def refuse_unless_throwaway(url: str) -> None:
    parsed = make_url(url)
    problems: list[str] = []
    if not parsed.drivername.startswith("postgresql"):
        problems.append(f"driver {parsed.drivername!r} is not PostgreSQL")
    name = parsed.database or ""
    if name.lower() in RUNTIME_DATABASES or not THROWAWAY_NAME.search(name):
        problems.append(f"database name {name!r} must contain 'rehears', 'throwaway' or 'scratch'")
    host = (parsed.host or "").lower()
    if host not in LOCAL_HOSTS and not THROWAWAY_NAME.search(host):
        problems.append(f"host {host!r} is not local or a rehearsal container")
    if parsed.port in {8000, 8010, 8011}:
        problems.append(f"port {parsed.port} is a runtime port")
    configured = os.environ.get("POSTGRES_RUNTIME_URL", "").strip()
    if configured:
        other = make_url(configured)
        if (other.host, other.port, other.database) == (parsed.host, parsed.port, parsed.database):
            problems.append("it is the configured runtime database (POSTGRES_RUNTIME_URL)")
    if problems:
        sys.exit("REFUSED: not a clearly throwaway database:\n  - " + "\n  - ".join(problems))


def refuse_unless_empty(engine) -> None:
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
        ).scalar()
    if tables:
        sys.exit(f"REFUSED: the rehearsal database is not empty ({tables} tables in schema public)")


# ---------------------------------------------------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------------------------------------------------
results: list[tuple[str, bool, str]] = []


def record(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))


def check(label: str, function) -> None:
    try:
        detail = function()
        record(label, True, detail or "")
    except AssertionError as error:
        record(label, False, str(error) or "assertion failed")
    except Exception as error:  # noqa: BLE001 - a rehearsal reports every failure, it does not stop at the first
        record(label, False, f"{type(error).__name__}: {str(error)[:200]}")


def report() -> int:
    width = max(len(label) for label, _, _ in results)
    print()
    print(f"{'PROBE'.ljust(width)}  RESULT  DETAIL")
    print(f"{'-' * width}  ------  ------")
    for label, ok, detail in results:
        print(f"{label.ljust(width)}  {'PASS' if ok else 'FAIL'}    {detail}")
    failed = [label for label, ok, _ in results if not ok]
    report_timings()
    print()
    print(f"{len(results) - len(failed)} PASS, {len(failed)} FAIL")
    if failed:
        print("FAILED: " + "; ".join(failed))
        return 1
    print("ALL PASS")
    return 0


# ---------------------------------------------------------------------------------------------------------------------
# Alembic plumbing
# ---------------------------------------------------------------------------------------------------------------------
def alembic_config(url: str, *, with_proposed: bool) -> Config:
    locations = [str(VERSIONS)] + ([str(PROPOSED)] if with_proposed else [])
    for location in locations:
        assert " " not in location, f"version location {location!r} contains a space; run from a path without one"
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.set_main_option("version_locations", " ".join(locations))
    cfg.set_main_option("path_separator", "space")
    return cfg


def current_revision(engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


# ---------------------------------------------------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------------------------------------------------
def column_info(engine, table: str, column: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT data_type, is_nullable, column_default, character_maximum_length FROM information_schema.columns"
                " WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        ).mappings().first()
    return dict(row) if row else None


def table_exists(engine, table: str) -> bool:
    with engine.connect() as conn:
        return bool(conn.execute(text("SELECT to_regclass(:n) IS NOT NULL"), {"n": f"public.{table}"}).scalar())


def index_def(engine, name: str) -> str | None:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"), {"n": name}
        ).scalar()


def trigger_names(engine, table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tgname FROM pg_trigger WHERE tgrelid = to_regclass(:t) AND NOT tgisinternal"
            ),
            {"t": f"public.{table}"},
        ).scalars().all()
    return set(rows)


def function_exists(engine, name: str) -> bool:
    with engine.connect() as conn:
        return bool(conn.execute(text("SELECT count(*) FROM pg_proc WHERE proname = :n"), {"n": name}).scalar())


def constraint_defs(engine, table: str) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = to_regclass(:t)"
            ),
            {"t": f"public.{table}"},
        ).all()
    return {name: definition for name, definition in rows}


def schema_signature(engine) -> dict:
    """Everything the migrations touch, in a comparable form: columns, indexes, constraints, triggers."""
    tables = sorted({table for table, _ in NEW_COLUMNS} | set(NEW_TABLES))
    signature: dict = {}
    with engine.connect() as conn:
        for table in tables:
            columns = conn.execute(
                text(
                    "SELECT column_name, data_type, is_nullable, column_default, character_maximum_length"
                    " FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :t"
                    " ORDER BY column_name"
                ),
                {"t": table},
            ).all()
            signature[f"columns:{table}"] = [tuple(row) for row in columns]
            indexes = conn.execute(
                text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = :t ORDER BY 1"),
                {"t": table},
            ).all()
            signature[f"indexes:{table}"] = [tuple(row) for row in indexes]
            signature[f"constraints:{table}"] = sorted(constraint_defs(engine, table).items())
            signature[f"triggers:{table}"] = sorted(trigger_names(engine, table))
        signature["functions"] = sorted(
            conn.execute(text("SELECT proname FROM pg_proc WHERE proname = 'essay_review_history_is_immutable'")).scalars()
        )
    return signature


def full_schema_signature(engine) -> dict:
    """Every public table: columns, indexes, constraints, triggers, plus user functions. Detects a downgrade that
    altered anything at all, not only the objects the upgrade added."""
    signature: dict = {}
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1")
        ).scalars().all()
        for table in tables:
            signature[f"columns:{table}"] = [
                tuple(row)
                for row in conn.execute(
                    text(
                        "SELECT column_name, data_type, is_nullable, column_default, character_maximum_length"
                        " FROM information_schema.columns WHERE table_schema = 'public' AND table_name = :t"
                        " ORDER BY column_name"
                    ),
                    {"t": table},
                ).all()
            ]
            signature[f"indexes:{table}"] = [
                tuple(row)
                for row in conn.execute(
                    text("SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' AND tablename = :t ORDER BY 1"),
                    {"t": table},
                ).all()
            ]
            signature[f"constraints:{table}"] = sorted(constraint_defs(engine, table).items())
            signature[f"triggers:{table}"] = sorted(trigger_names(engine, table))
        signature["functions"] = sorted(
            conn.execute(
                text(
                    "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
                    " WHERE n.nspname = 'public'"
                )
            ).scalars()
        )
    return signature


def seed_volume(engine, rows: int, now) -> None:
    """`rows` rows in each hot table, in SQL, at revision 0016 (before any new column exists)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                " SELECT gen_random_uuid(), 'vol-' || g, 'vol-' || g || '@example.test', '', '', 'user', :now"
                " FROM generate_series(1, :n) g"
            ),
            {"n": rows, "now": now},
        )
        conn.execute(text("CREATE TEMP TABLE vol_users AS SELECT id, row_number() OVER () AS n FROM users WHERE user_key LIKE 'vol-%'"))
        conn.execute(
            text(
                "INSERT INTO user_language_profiles (id, user_id, language_code, goal, style, pinyin, native_language,"
                " theme_preset, created_at, updated_at)"
                " SELECT gen_random_uuid(), id, 'en', 'everyday', 'guided', 'auto', 'vi', 'editorial', :now, :now"
                " FROM vol_users"
            ),
            {"now": now},
        )
        conn.execute(
            text(
                "INSERT INTO library_items (id, user_id, language_code, kind, saved_word_id, source_id, relationship,"
                " created_at, updated_at) SELECT gen_random_uuid(), id, 'en', 'reading', NULL, 'vol:' || n, 'started',"
                " :now, :now FROM vol_users"
            ),
            {"now": now},
        )
        conn.execute(
            text(
                "INSERT INTO grammar_progress (id, user_id, language_code, lesson_id, completed_at)"
                " SELECT gen_random_uuid(), id, 'en', 'vol.point.' || n, :now FROM vol_users"
            ),
            {"now": now},
        )
        conn.execute(
            text(
                "INSERT INTO listening_progress (id, user_id, language_code, asset_id, segment_id, presentation, revealed,"
                " checked_attempt_count, best_accuracy_percent, best_exact, last_answer, last_used_hint, last_hint_level,"
                " updated_at) SELECT gen_random_uuid(), id, 'en', 'vol-asset', 'seg-' || n, 'checked', false, 1, 70,"
                " false, 'x', false, 0, :now FROM vol_users"
            ),
            {"now": now},
        )
        conn.execute(
            text(
                "INSERT INTO essays (id, user_id, language_code, legacy_id, created_at, prompt, text, word_count,"
                " target_level, grammar, vocabulary, coherence, task_achievement, naturalness, overall, level_estimate,"
                " evaluator, summary_vi, strengths, priorities, errors, module_data, strength_evidence)"
                " SELECT gen_random_uuid(), id, 'en', 1, :now, '', 'volume seed', 2, '', 60, 60, 60, 60, 60, 60, '',"
                " 'rehearsal', '', '[]', '[]', '[]', '{}', '[]' FROM vol_users"
            ),
            {"now": now},
        )
        conn.execute(text("DROP TABLE vol_users"))


timings: list[tuple[str, str, float]] = []


def apply_one_by_one(cfg, revisions, *, direction: str, label: str) -> None:
    """One `alembic` invocation per revision, timed. The elapsed time is the upper bound of how long the revision's
    locks were held: it includes the transaction's commit, and the connection setup."""
    for revision in revisions:
        started = time.monotonic()
        if direction == "up":
            command.upgrade(cfg, revision)
        else:
            command.downgrade(cfg, revision)
        timings.append((label, revision, time.monotonic() - started))


def report_timings() -> None:
    if not timings:
        return
    print()
    print("LOCK-HOLD TIMES (one invocation per revision; the locks are held at most this long)")
    print(f"{'run'.ljust(24)}  {'revision'.ljust(14)}  seconds")
    for label, revision, seconds in timings:
        print(f"{label.ljust(24)}  {revision.ljust(14)}  {seconds:8.3f}")
    slowest = max(timings, key=lambda item: item[2])
    print(f"slowest: {slowest[1]} in {slowest[0]}: {slowest[2]:.3f} s")


def refuses(engine, label: str, statement: str, params: dict, expect: str) -> None:
    def run() -> str:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement), params)
        except (IntegrityError, DBAPIError) as error:
            message = str(error.orig if hasattr(error, "orig") else error)
            assert expect in message, f"expected {expect!r} in {message[:160]!r}"
            return f"refused ({expect})"
        raise AssertionError("the database accepted what it must refuse")

    check(label, run)


def accepts(engine, label: str, statement: str, params: dict) -> None:
    def run() -> str:
        with engine.begin() as conn:
            conn.execute(text(statement), params)
        return "accepted"

    check(label, run)


# ---------------------------------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------------------------------
def main() -> int:
    args = sys.argv[1:]
    volume = 0
    if "--volume" in args:
        at = args.index("--volume")
        try:
            volume = int(args[at + 1])
        except (IndexError, ValueError):
            print("--volume needs a whole number of rows")
            return 2
        assert volume >= 0
        del args[at:at + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    url = args[0]
    refuse_unless_throwaway(url)
    engine = create_engine(url)
    refuse_unless_empty(engine)
    now = datetime.now(UTC)

    # ---- 1. the chain to 0016 from versions/ only, then rows that exist before the new columns
    command.upgrade(alembic_config(url, with_proposed=False), BASE)
    check("chain built to 20260924_0016 from versions/", lambda: (
        current_revision(engine) == BASE or (_ for _ in ()).throw(AssertionError(current_revision(engine)))
    ) and BASE)
    check("no proposed revision is visible without version_locations", lambda: (
        ScriptDirectory.from_config(alembic_config(url, with_proposed=False)).get_heads() == [BASE]
        or (_ for _ in ()).throw(AssertionError("versions/ has a head other than 0016"))
    ) and "single head 0016")

    baseline_signature = full_schema_signature(engine)
    record("schema captured at 20260924_0016 (all public tables)", True,
           f"{len([k for k in baseline_signature if k.startswith('columns:')])} tables")

    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    essay_a = uuid.uuid4()
    with engine.begin() as conn:
        for user in (user_a, user_b):
            conn.execute(
                text(
                    "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                    " VALUES (:id, :key, :email, '', '', 'user', :now)"
                ),
                {"id": user, "key": f"rehearsal-{user}", "email": f"{user}@example.test", "now": now},
            )
        for user, lang in ((user_a, "en"), (user_a, "zh"), (user_b, "en")):
            conn.execute(
                text(
                    "INSERT INTO user_language_profiles (id, user_id, language_code, goal, style, pinyin,"
                    " native_language, theme_preset, created_at, updated_at)"
                    " VALUES (:id, :u, :l, 'everyday', 'guided', 'auto', 'vi', 'editorial', :now, :now)"
                ),
                {"id": uuid.uuid4(), "u": user, "l": lang, "now": now},
            )
        conn.execute(
            text(
                "INSERT INTO listening_progress (id, user_id, language_code, asset_id, segment_id, presentation,"
                " revealed, checked_attempt_count, best_accuracy_percent, best_exact, last_answer, last_used_hint,"
                " last_hint_level, updated_at) VALUES (:id, :u, 'en', 'asset-1', 'seg-1', 'checked', false, 2, 88,"
                " false, 'hello', false, 0, :now)"
            ),
            {"id": uuid.uuid4(), "u": user_a, "now": now},
        )
        conn.execute(
            text(
                "INSERT INTO grammar_progress (id, user_id, language_code, lesson_id, completed_at)"
                " VALUES (:id, :u, 'en', 'a1-basic-prepositions-of-time', :now)"
            ),
            {"id": uuid.uuid4(), "u": user_a, "now": now},
        )
        conn.execute(
            text(
                "INSERT INTO library_items (id, user_id, language_code, kind, saved_word_id, source_id,"
                " relationship, created_at, updated_at) VALUES (:id, :u, 'en', 'reading', NULL, 'article:seed',"
                " 'started', :now, :now)"
            ),
            {"id": uuid.uuid4(), "u": user_a, "now": now},
        )
        conn.execute(
            text(
                "INSERT INTO essays (id, user_id, language_code, legacy_id, created_at, prompt, text, word_count,"
                " target_level, grammar, vocabulary, coherence, task_achievement, naturalness, overall,"
                " level_estimate, evaluator, summary_vi, strengths, priorities, errors, module_data,"
                " strength_evidence) VALUES (:id, :u, 'zh', 1, :now, '', :text, 3, '', 70, 70, 70, 70, 70, 70, '',"
                " 'rehearsal', '', '[]', '[]', '[]', '{}', '[]')"
            ),
            {"id": essay_a, "u": user_a, "now": now, "text": "我喜欢学习"},
        )

    def counts() -> dict[str, int]:
        with engine.connect() as conn:
            return {
                table: conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                for table in ("users", "user_language_profiles", "listening_progress", "grammar_progress",
                              "library_items", "essays")
            }

    if volume:
        started = time.monotonic()
        seed_volume(engine, volume, now)
        record(f"volume seed: {volume} rows in each hot table", True, f"{time.monotonic() - started:.1f}s to seed")
    seeded = counts()
    record("rows seeded before the new columns exist", True, str(seeded))

    # ---- 2. lock_timeout is written into every revision, guarded by dialect
    def lock_timeout_in_files() -> str:
        for revision in NEW_REVISIONS:
            path = next(PROPOSED.glob(f"{revision}_*.py"))
            source = path.read_text(encoding="utf-8")
            assert "SET LOCAL lock_timeout" in source, f"{path.name} has no lock_timeout"
            assert 'dialect.name == "postgresql"' in source, f"{path.name} does not guard it by dialect"
        return f"{len(NEW_REVISIONS)} files"

    check("every revision sets lock_timeout, guarded by dialect", lock_timeout_in_files)

    # ---- 3. upgrade to head with proposed/ visible
    proposed_cfg = alembic_config(url, with_proposed=True)
    check("proposed revisions form one linear chain after 0016", lambda: (
        _chain_ok(proposed_cfg) or (_ for _ in ()).throw(AssertionError("chain is not 0016 -> 0017 ... -> 0023"))
    ) and "0016 -> 0017 -> ... -> 0023, single head")
    apply_one_by_one(proposed_cfg, NEW_REVISIONS, direction="up", label="first upgrade")
    check("upgraded to head, one revision per invocation", lambda: (
        current_revision(engine) == HEAD or (_ for _ in ()).throw(AssertionError(current_revision(engine)))
    ) and HEAD)

    probe_schema(engine, user_a, user_b, essay_a, now, seeded, counts)
    first_signature = schema_signature(engine)

    # ---- 4. lock_timeout in action: downgrade from head blocked by a lock on users
    lock_probe(engine, url, proposed_cfg, direction="downgrade", holder_table="users")

    # ---- 5. up -> down to 0016 -> up
    command.downgrade(proposed_cfg, BASE)
    check("downgraded to 20260924_0016", lambda: (
        current_revision(engine) == BASE or (_ for _ in ()).throw(AssertionError(current_revision(engine)))
    ) and BASE)

    def everything_removed() -> str:
        for table, column in NEW_COLUMNS:
            assert column_info(engine, table, column) is None, f"{table}.{column} survived the downgrade"
        for table in NEW_TABLES:
            assert not table_exists(engine, table), f"{table} survived the downgrade"
        for name in NEW_INDEXES:
            assert index_def(engine, name) is None, f"index {name} survived the downgrade"
        assert not function_exists(engine, "essay_review_history_is_immutable"), "trigger function survived"
        assert "ck_grammar_progress_quiz" not in constraint_defs(engine, "grammar_progress"), "check survived"
        return "columns, table, indexes, trigger function and check are gone"

    check("downgrade removes everything the upgrade added", everything_removed)
    check("schema after the downgrade equals the schema captured at 20260924_0016", lambda: (
        full_schema_signature(engine) == baseline_signature
        or (_ for _ in ()).throw(AssertionError(_signature_diff(baseline_signature, full_schema_signature(engine))))
    ) and "every public table identical: columns, indexes, constraints, triggers, functions")
    def old_rows_survive() -> str:
        after = counts()
        short = {t: (after[t], n) for t, n in seeded.items() if after[t] < n}
        assert not short, f"rows were lost by the downgrade: {short}"
        with engine.connect() as conn:
            kept = conn.execute(
                text("SELECT best_accuracy_percent FROM listening_progress WHERE asset_id = 'asset-1'")
            ).scalar()
        assert kept == 88, f"the seeded listening row reads {kept}"
        return f"every seeded row is still there ({after})"

    check("old rows survive the downgrade", old_rows_survive)

    lock_probe(engine, url, proposed_cfg, direction="upgrade", holder_table="users")

    apply_one_by_one(proposed_cfg, NEW_REVISIONS, direction="up", label="second upgrade")
    check("upgraded to head again", lambda: (
        current_revision(engine) == HEAD or (_ for _ in ()).throw(AssertionError(current_revision(engine)))
    ) and HEAD)
    check("schema after up-down-up equals the schema after the first upgrade", lambda: (
        schema_signature(engine) == first_signature
        or (_ for _ in ()).throw(AssertionError(_signature_diff(first_signature, schema_signature(engine))))
    ) and "identical columns, indexes, constraints, triggers")
    probe_defaults_again(engine, user_a, user_b, seeded, counts)

    # ---- 6. concurrency on the history unique key
    race_history(engine, now)

    return report()


def _chain_ok(cfg: Config) -> bool:
    script = ScriptDirectory.from_config(cfg)
    if script.get_heads() != [HEAD]:
        return False
    revisions = [revision.revision for revision in script.walk_revisions()]
    return list(reversed(revisions))[-8:] == [BASE, *NEW_REVISIONS]


def _signature_diff(first: dict, second: dict) -> str:
    keys = [key for key in first if first[key] != second.get(key)]
    return "differs in " + ", ".join(keys)


# ---------------------------------------------------------------------------------------------------------------------
# Probes at head
# ---------------------------------------------------------------------------------------------------------------------
def expect_column(engine, table, column, data_type, nullable, default_contains=None, length=None):
    def run() -> str:
        info = column_info(engine, table, column)
        assert info is not None, "column is missing"
        assert info["data_type"] == data_type, f"type {info['data_type']!r}, want {data_type!r}"
        assert (info["is_nullable"] == "YES") == nullable, f"nullable={info['is_nullable']}, want {nullable}"
        if default_contains is None:
            assert info["column_default"] is None, f"unexpected default {info['column_default']!r}"
        else:
            assert default_contains in (info["column_default"] or ""), f"default {info['column_default']!r}"
        if length is not None:
            assert info["character_maximum_length"] == length, f"length {info['character_maximum_length']}"
        return f"{info['data_type']} {'NULL' if nullable else 'NOT NULL'} default={info['column_default']}"

    check(f"{table}.{column}", run)


def probe_schema(engine, user_a, user_b, essay_a, now, seeded, counts) -> None:
    # 0017, 0019: user_language_profiles
    expect_column(engine, "user_language_profiles", "declared_level", "character varying", False, "''", 20)
    expect_column(engine, "user_language_profiles", "review_new_per_day", "smallint", True)
    expect_column(engine, "user_language_profiles", "review_limit_per_day", "smallint", True)
    expect_column(engine, "user_language_profiles", "review_modes", "json", True)
    # 0018: users
    expect_column(engine, "users", "learning_language", "character varying", False, "''", 20)
    expect_column(engine, "users", "interface_language", "character varying", False, "''", 8)
    expect_column(engine, "users", "weekly_goal_days", "smallint", True)
    expect_column(engine, "users", "settings_updated_at", "timestamp with time zone", True)
    # 0020: listening_progress
    expect_column(engine, "listening_progress", "score_source", "character varying", False, "'client'", 12)
    # 0022: library_items
    expect_column(engine, "library_items", "place", "json", True)
    expect_column(engine, "library_items", "place_at", "timestamp with time zone", True)
    # 0023: grammar_progress
    expect_column(engine, "grammar_progress", "last_quiz_correct", "smallint", True)
    expect_column(engine, "grammar_progress", "last_quiz_total", "smallint", True)
    expect_column(engine, "grammar_progress", "last_quiz_at", "timestamp with time zone", True)

    probe_defaults_again(engine, user_a, user_b, seeded, counts)

    # users.settings_updated_at is the server-owned version token: a conditional update lands once
    def conditional_update() -> str:
        token = datetime.now(UTC)
        sql = (
            "UPDATE users SET learning_language = 'zh', settings_updated_at = :new"
            " WHERE id = :id AND settings_updated_at IS NOT DISTINCT FROM :expected"
        )
        with engine.begin() as conn:
            first = conn.execute(text(sql), {"new": token, "id": user_b, "expected": None}).rowcount
        with engine.begin() as conn:
            stale = conn.execute(text(sql), {"new": token, "id": user_b, "expected": None}).rowcount
        with engine.begin() as conn:
            fresh = conn.execute(
                text(sql), {"new": datetime.now(UTC), "id": user_b, "expected": token}
            ).rowcount
        assert (first, stale, fresh) == (1, 0, 1), f"rowcounts {(first, stale, fresh)}, want (1, 0, 1)"
        return "NULL token -> 1 row; the same stale token -> 0 rows; the current token -> 1 row"

    check("users.settings_updated_at: conditional update (expected version)", conditional_update)

    # 0018 must not disturb the RESTRICT that keeps the users row
    def users_restrict_untouched() -> str:
        with engine.connect() as conn:
            rule = conn.execute(
                text(
                    "SELECT confdeltype FROM pg_constraint WHERE conrelid = to_regclass('public.account_incarnations')"
                    " AND contype = 'f' AND confrelid = to_regclass('public.users')"
                )
            ).scalar()
        assert rule == "r", f"account_incarnations.user_id delete rule is {rule!r}, want 'r' (RESTRICT)"
        return "account_incarnations.user_id -> users is still ON DELETE RESTRICT"

    check("users row still protected by the incarnation RESTRICT", users_restrict_untouched)

    # 0020: a new insert that does not name score_source reads 'client'
    def score_source_default_on_insert() -> str:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO listening_progress (id, user_id, language_code, asset_id, segment_id, presentation,"
                    " revealed, checked_attempt_count, best_exact, last_answer, last_used_hint, last_hint_level,"
                    " updated_at) VALUES (:id, :u, 'en', 'asset-2', 'seg-1', 'prompt', false, 0, false, '', false, 0,"
                    " :now)"
                ),
                {"id": uuid.uuid4(), "u": user_b, "now": now},
            )
            value = conn.execute(
                text("SELECT score_source FROM listening_progress WHERE asset_id = 'asset-2'")
            ).scalar()
        assert value == "client", value
        return "an insert that predates the column reads 'client'"

    check("listening_progress.score_source: default on insert", score_source_default_on_insert)

    # 0021: essay_review_history
    def history_shape() -> str:
        assert table_exists(engine, "essay_review_history"), "table missing"
        cols = {
            name: column_info(engine, "essay_review_history", name)
            for name in ("id", "essay_id", "superseded_at", "reason",
                         "prior_fingerprint", "prior_contract", "replaced_by_fingerprint", "review")
        }
        assert all(cols.values()), [n for n, v in cols.items() if not v]
        assert all(info["is_nullable"] == "NO" for info in cols.values()), "every column is NOT NULL"
        assert cols["review"]["data_type"] == "json"
        assert cols["id"]["data_type"] == "uuid" and cols["essay_id"]["data_type"] == "uuid"
        defs = constraint_defs(engine, "essay_review_history")
        assert "uq_essay_review_history_prior" in defs and "essay_id, prior_fingerprint" in defs[
            "uq_essay_review_history_prior"], defs
        assert column_info(engine, "essay_review_history", "user_id") is None, "a user_id copy survived"
        assert column_info(engine, "essay_review_history", "language_code") is None, "a language_code copy survived"
        assert "essay_id, superseded_at" in (index_def(engine, "ix_essay_review_history_essay") or ""), "index"
        return "8 NOT NULL columns (no scope copy), json review, unique (essay_id, prior_fingerprint), index (essay_id, superseded_at)"

    check("essay_review_history: shape (scope is the essay's), unique key and index", history_shape)

    def trigger_present() -> str:
        assert "essay_review_history_immutable" in trigger_names(engine, "essay_review_history"), "trigger missing"
        with engine.connect() as conn:
            definition = conn.execute(
                text(
                    "SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE tgname = 'essay_review_history_immutable'"
                )
            ).scalar()
        assert "BEFORE UPDATE" in definition and "DELETE" not in definition, definition
        return "BEFORE UPDATE only (a DELETE trigger would block the cascade)"

    check("essay_review_history: immutability trigger is UPDATE only", trigger_present)

    history_id = uuid.uuid4()
    insert = (
        "INSERT INTO essay_review_history (id, essay_id, superseded_at, reason,"
        " prior_fingerprint, prior_contract, replaced_by_fingerprint, review)"
        " VALUES (:id, :essay, :now, 'evaluator_refresh', :prior, 'writing-evaluation-v2.6', :new,"
        " CAST(:review AS json))"
    )
    base = {
        "essay": essay_a, "now": now, "new": "n" * 64,
        "review": '{"overall": 70, "errors": []}',
    }
    accepts(engine, "essay_review_history: a prior review is accepted",
            insert, {**base, "id": history_id, "prior": "a" * 64})
    refuses(engine, "essay_review_history: the same prior review twice", insert,
            {**base, "id": uuid.uuid4(), "prior": "a" * 64}, "uq_essay_review_history_prior")
    refuses(engine, "essay_review_history: an unknown essay",
            insert, {**base, "id": uuid.uuid4(), "essay": uuid.uuid4(), "prior": "b" * 64},
            "essay_review_history_essay_id_fkey")
    refuses(engine, "essay_review_history: an UPDATE is rejected by the trigger",
            "UPDATE essay_review_history SET reason = 'changed' WHERE id = :id", {"id": history_id}, "immutable")

    def cascade_on_essay_delete() -> str:
        extra_essay = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO essays (id, user_id, language_code, legacy_id, created_at, prompt, text, word_count,"
                    " target_level, grammar, vocabulary, coherence, task_achievement, naturalness, overall,"
                    " level_estimate, evaluator, summary_vi, strengths, priorities, errors, module_data,"
                    " strength_evidence) VALUES (:id, :u, 'zh', 2, :now, '', 'x', 1, '', 1, 1, 1, 1, 1, 1, '', 'r',"
                    " '', '[]', '[]', '[]', '{}', '[]')"
                ),
                {"id": extra_essay, "u": user_a, "now": now},
            )
            conn.execute(text(insert), {**base, "id": uuid.uuid4(), "essay": extra_essay, "prior": "c" * 64})
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM essays WHERE id = :id"), {"id": extra_essay})
        with engine.connect() as conn:
            left = conn.execute(
                text("SELECT count(*) FROM essay_review_history WHERE essay_id = :id"), {"id": extra_essay}
            ).scalar()
        assert left == 0, f"{left} history rows survived the essay's deletion"
        return "deleting the essay deleted its history (the DELETE is not blocked by the UPDATE trigger)"

    check("essay_review_history: cascade on essay delete", cascade_on_essay_delete)

    def cascade_on_user_delete() -> str:
        temp_user, temp_essay = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                    " VALUES (:id, :key, :email, '', '', 'user', :now)"
                ),
                {"id": temp_user, "key": f"rehearsal-{temp_user}", "email": f"{temp_user}@example.test", "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO essays (id, user_id, language_code, legacy_id, created_at, prompt, text, word_count,"
                    " target_level, grammar, vocabulary, coherence, task_achievement, naturalness, overall,"
                    " level_estimate, evaluator, summary_vi, strengths, priorities, errors, module_data,"
                    " strength_evidence) VALUES (:id, :u, 'zh', 1, :now, '', 'x', 1, '', 1, 1, 1, 1, 1, 1, '', 'r',"
                    " '', '[]', '[]', '[]', '{}', '[]')"
                ),
                {"id": temp_essay, "u": temp_user, "now": now},
            )
            conn.execute(text(insert), {**base, "id": uuid.uuid4(), "essay": temp_essay, "prior": "d" * 64})
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": temp_user})
        with engine.connect() as conn:
            left = conn.execute(
                text("SELECT count(*) FROM essay_review_history WHERE essay_id = :id"), {"id": temp_essay}
            ).scalar()
        assert left == 0, f"{left} history rows survived the user's deletion"
        return "deleting the user deleted its essays and, through them, the history"

    check("essay_review_history: cascade on user delete (through the essays)", cascade_on_user_delete)

    # 0022: library_items
    def place_index() -> str:
        definition = index_def(engine, "ix_library_items_place") or ""
        assert "user_id, language_code, place_at" in definition, definition
        assert "WHERE (place IS NOT NULL)" in definition, definition
        return "partial index (user_id, language_code, place_at) WHERE place IS NOT NULL"

    check("library_items: partial place index", place_index)

    place_upsert = (
        "INSERT INTO library_items (id, user_id, language_code, kind, saved_word_id, source_id, relationship,"
        " created_at, updated_at, place, place_at) VALUES (:id, :u, 'en', 'reading', NULL, :s, 'started', :created,"
        " :created, CAST(:p AS json), :at)"
        " ON CONFLICT (user_id, language_code, kind, source_id, relationship) WHERE saved_word_id IS NULL"
        " DO UPDATE SET place = EXCLUDED.place, place_at = EXCLUDED.place_at"
        " WHERE (CAST(:boundary AS boolean) OR library_items.place_at IS NULL"
        " OR library_items.place_at <= EXCLUDED.place_at - interval '30 seconds')"
        " RETURNING version, updated_at, place_at"
    )

    def place_write_semantics() -> str:
        """The write I4 specifies: created on first open, coalesced within 30 s unless a boundary, never touching
        version or updated_at, so a concurrent pin/note PATCH still lands."""
        from datetime import timedelta

        item_source = f"article:place-{uuid.uuid4()}"
        t0 = datetime.now(UTC)

        def write(seconds: int, boundary: bool, index: int):
            with engine.begin() as conn:
                return conn.execute(
                    text(place_upsert),
                    {"id": uuid.uuid4(), "u": user_a, "s": item_source, "created": t0, "at": t0 + timedelta(seconds=seconds),
                     "p": f'{{"index": {index}, "total": 10}}', "boundary": boundary},
                ).first()

        first = write(0, False, 1)
        assert first is not None and first[0] == 1, f"first open did not create the started row: {first}"
        created_updated_at = first[1]
        assert write(5, False, 2) is None, "a non-boundary write 5 s later was not coalesced"
        boundary = write(5, True, 3)
        assert boundary is not None, "a boundary write was coalesced"
        later = write(40, False, 4)
        assert later is not None, "a write 35 s after the last one was coalesced"
        with engine.begin() as conn:
            row = conn.execute(
                text("SELECT version, updated_at, (place->>'index')::int FROM library_items"
                     " WHERE user_id = :u AND source_id = :s AND relationship = 'started'"),
                {"u": user_a, "s": item_source},
            ).one()
        assert (row[0], row[1], row[2]) == (1, created_updated_at, 4), f"row after the writes: {tuple(row)}"
        with engine.begin() as conn:
            pinned = conn.execute(
                text("UPDATE library_items SET pinned_at = :now, version = version + 1"
                     " WHERE user_id = :u AND source_id = :s AND relationship = 'started' AND version = 1"),
                {"now": t0, "u": user_a, "s": item_source},
            ).rowcount
        assert pinned == 1, "a pin PATCH with the version it read conflicted after place writes"
        return ("created; 5 s non-boundary coalesced; boundary and +35 s written; version 1 and updated_at unchanged;"
                " a pin at version 1 still lands")

    check("library_items: place upsert (coalescing, version untouched, pin unaffected)", place_write_semantics)

    def json_null_is_not_sql_null() -> str:
        item_source = f"article:jsonnull-{uuid.uuid4()}"
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO library_items (id, user_id, language_code, kind, saved_word_id, source_id, relationship,"
                    " created_at, updated_at, place, place_at) VALUES (:id, :u, 'en', 'reading', NULL, :s, 'started',"
                    " :now, :now, CAST('null' AS json), NULL)"
                ),
                {"id": uuid.uuid4(), "u": user_a, "s": item_source, "now": now},
            )
            is_set = conn.execute(
                text("SELECT place IS NOT NULL FROM library_items WHERE source_id = :s"), {"s": item_source}
            ).scalar()
            conn.execute(text("DELETE FROM library_items WHERE source_id = :s"), {"s": item_source})
        assert is_set is True, "a JSON null read as SQL NULL"
        return ("a JSON null satisfies `place IS NOT NULL` and would enter the partial index: the ORM must declare "
                "`place` and `review_modes` with none_as_null=True (proposal section 15)")

    check("library_items: JSON null is not SQL NULL (the hazard the ORM must avoid)", json_null_is_not_sql_null)

    # A runtime still at the old code after a rollback inserts without the new columns.
    def old_code_inserts() -> str:
        old_user, old_profile = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                     " VALUES (:id, :k, :e, '', '', 'user', :now)"),
                {"id": old_user, "k": f"oldcode-{old_user}", "e": f"{old_user}@example.test", "now": now},
            )
            conn.execute(
                text("INSERT INTO user_language_profiles (id, user_id, language_code, goal, style, pinyin,"
                     " native_language, theme_preset, created_at, updated_at)"
                     " VALUES (:id, :u, 'en', 'everyday', 'guided', 'auto', 'vi', 'editorial', :now, :now)"),
                {"id": old_profile, "u": old_user, "now": now},
            )
            user_row = conn.execute(
                text("SELECT learning_language, interface_language, weekly_goal_days, settings_updated_at"
                     " FROM users WHERE id = :id"), {"id": old_user}).one()
            profile_row = conn.execute(
                text("SELECT declared_level, review_new_per_day, review_limit_per_day, review_modes"
                     " FROM user_language_profiles WHERE id = :id"), {"id": old_profile}).one()
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": old_user})
        assert tuple(user_row) == ("", "", None, None), tuple(user_row)
        assert tuple(profile_row) == ("", None, None, None), tuple(profile_row)
        return "an old-code insert into users and user_language_profiles succeeds and reads the defaults"

    check("old-code inserts (no new columns) into users and user_language_profiles", old_code_inserts)

    # 0023: grammar_progress check
    gp = (
        "INSERT INTO grammar_progress (id, user_id, language_code, lesson_id, completed_at, last_quiz_correct,"
        " last_quiz_total, last_quiz_at) VALUES (:id, :u, 'en', :lesson, :now, :c, :t, :at)"
    )
    gbase = {"u": user_b, "now": now}
    accepts(engine, "grammar_progress: a complete quiz result", gp,
            {**gbase, "id": uuid.uuid4(), "lesson": "en.present_perfect", "c": 4, "t": 5, "at": now})
    accepts(engine, "grammar_progress: completion with no quiz result", gp,
            {**gbase, "id": uuid.uuid4(), "lesson": "en.past_simple", "c": None, "t": None, "at": None})
    refuses(engine, "grammar_progress: correct greater than total", gp,
            {**gbase, "id": uuid.uuid4(), "lesson": "en.x1", "c": 6, "t": 5, "at": now}, "ck_grammar_progress_quiz")
    refuses(engine, "grammar_progress: a total without a time", gp,
            {**gbase, "id": uuid.uuid4(), "lesson": "en.x2", "c": 1, "t": 5, "at": None}, "ck_grammar_progress_quiz")
    refuses(engine, "grammar_progress: a zero total", gp,
            {**gbase, "id": uuid.uuid4(), "lesson": "en.x3", "c": 0, "t": 0, "at": now}, "ck_grammar_progress_quiz")


def probe_defaults_again(engine, user_a, user_b, seeded, counts) -> None:
    """What rows that existed before the migrations read afterwards. Run at head, and again after up-down-up."""

    def old_rows_default() -> str:
        with engine.connect() as conn:
            level = conn.execute(text("SELECT DISTINCT declared_level FROM user_language_profiles")).scalars().all()
            review = conn.execute(
                text("SELECT count(*) FROM user_language_profiles WHERE review_new_per_day IS NOT NULL"
                     " OR review_limit_per_day IS NOT NULL OR review_modes IS NOT NULL")
            ).scalar()
            users = conn.execute(
                text("SELECT learning_language, interface_language FROM users WHERE id = :a"), {"a": user_a}
            ).one()
            goal = conn.execute(
                text("SELECT weekly_goal_days, settings_updated_at FROM users WHERE id = :a"), {"a": user_a}
            ).one()
            score = conn.execute(
                text("SELECT score_source, best_accuracy_percent FROM listening_progress WHERE asset_id = 'asset-1'")
            ).one()
            place = conn.execute(
                text("SELECT count(*) FROM library_items WHERE user_id = :a AND source_id = 'article:seed'"
                     " AND place IS NULL AND place_at IS NULL"), {"a": user_a}
            ).scalar()
            quiz = conn.execute(
                text("SELECT last_quiz_correct, last_quiz_total, last_quiz_at FROM grammar_progress"
                     " WHERE user_id = :a"), {"a": user_a}
            ).one()
        assert level == [""], level
        assert review == 0, review
        assert tuple(users) == ("", ""), tuple(users)
        assert tuple(goal) == (None, None), tuple(goal)
        assert tuple(score) == ("client", 88), tuple(score)
        assert place == 1, "the seeded started row's place is not NULL"
        assert tuple(quiz) == (None, None, None), tuple(quiz)
        return "declared_level '', review NULL, users '' '' NULL NULL, score_source 'client' (88 kept), place NULL, quiz NULL"

    check("rows that predate the migrations read the defaults", old_rows_default)


# ---------------------------------------------------------------------------------------------------------------------
# lock_timeout in action
# ---------------------------------------------------------------------------------------------------------------------
def lock_probe(engine, url: str, cfg: Config, *, direction: str, holder_table: str) -> None:
    label = f"lock_timeout: {direction} refused within seconds while {holder_table} is locked; nothing half-applied"

    def run() -> str:
        before = current_revision(engine)
        holder = engine.connect()
        transaction = holder.begin()
        try:
            # ACCESS SHARE conflicts with the ACCESS EXCLUSIVE lock that ALTER TABLE takes.
            holder.execute(text(f"LOCK TABLE {holder_table} IN ACCESS SHARE MODE"))
            started = time.monotonic()
            failure: BaseException | None = None
            try:
                if direction == "downgrade":
                    command.downgrade(cfg, BASE)
                else:
                    command.upgrade(cfg, "head")
            except BaseException as error:  # noqa: BLE001
                failure = error
            elapsed = time.monotonic() - started
        finally:
            transaction.rollback()
            holder.close()
        assert failure is not None, "the migration ran although the table was locked (no lock_timeout?)"
        message = str(getattr(failure, "orig", failure))
        sqlstate = getattr(getattr(failure, "orig", None), "sqlstate", None)
        assert sqlstate == "55P03" or "lock timeout" in message.lower(), f"unexpected failure: {message[:160]}"
        assert 3.0 <= elapsed <= 20.0, f"it gave up after {elapsed:.1f}s, expected about 5s"
        assert current_revision(engine) == before, "the revision moved although the migration failed"
        # Atomic: a failure at the first ALTER on `users` must have rolled the whole run back.
        present = column_info(engine, "users", "learning_language") is not None
        assert present == (before == HEAD), "a column of 0018 is in the wrong state after the failed run"
        return f"55P03 after {elapsed:.1f}s; still at {before}"

    check(label, run)


# ---------------------------------------------------------------------------------------------------------------------
# Concurrency on the history unique key
# ---------------------------------------------------------------------------------------------------------------------
def race_history(engine, now) -> None:
    def run() -> str:
        race_user, race_essay = uuid.uuid4(), uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO users (id, user_key, email, name, picture, role, created_at)"
                    " VALUES (:id, :key, :email, '', '', 'user', :now)"
                ),
                {"id": race_user, "key": f"race-{race_user}", "email": f"{race_user}@example.test", "now": now},
            )
            conn.execute(
                text(
                    "INSERT INTO essays (id, user_id, language_code, legacy_id, created_at, prompt, text, word_count,"
                    " target_level, grammar, vocabulary, coherence, task_achievement, naturalness, overall,"
                    " level_estimate, evaluator, summary_vi, strengths, priorities, errors, module_data,"
                    " strength_evidence) VALUES (:id, :u, 'zh', 1, :now, '', 'x', 1, '', 1, 1, 1, 1, 1, 1, '', 'r',"
                    " '', '[]', '[]', '[]', '{}', '[]')"
                ),
                {"id": race_essay, "u": race_user, "now": now},
            )
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        guard = threading.Lock()

        def refresh() -> None:
            barrier.wait()
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO essay_review_history (id, essay_id, superseded_at,"
                            " reason, prior_fingerprint, prior_contract, replaced_by_fingerprint, review)"
                            " VALUES (:id, :e, :now, 'evaluator_refresh', :p, 'writing-evaluation-v2.6',"
                            " :n, CAST('{}' AS json))"
                        ),
                        {"id": uuid.uuid4(), "e": race_essay, "now": now, "p": "f" * 64, "n": "g" * 64},
                    )
                result = "inserted"
            except (IntegrityError, DBAPIError) as error:
                result = "refused" if "uq_essay_review_history_prior" in str(error.orig) else f"other: {error}"
            with guard:
                outcomes.append(result)

        threads = [threading.Thread(target=refresh) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        with engine.begin() as conn:
            rows = conn.execute(
                text("SELECT count(*) FROM essay_review_history WHERE essay_id = :e"), {"e": race_essay}
            ).scalar()
            conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": race_user})
        assert sorted(outcomes) == ["inserted", "refused"], outcomes
        assert rows == 1, rows
        return "two simultaneous refreshes of one prior review: one row, one refusal"

    check("essay_review_history: two writers, one prior review", run)


if __name__ == "__main__":
    sys.exit(main())
