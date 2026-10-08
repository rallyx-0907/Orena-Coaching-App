"""The production migration pack (D-143): one tool that takes the product runtime (:8000) from the schema
revision its backup recorded to this checkout's head, the same way on the restored copy and on :8000.

    python scripts/product_migration_pack.py digest
        print this checkout's chain head and chain digest (no database)

    python scripts/product_migration_pack.py rehearse --backup <folder> --confirm-rehearsal <database>
        on a RESTORED COPY: check it reproduces the backup, apply the chain one revision per step, verify, and
        print one JSON report line (REPORT=...). `product_migration_rehearsal.ps1` runs this and writes it to
        rehearsal.json beside the backup.

    python scripts/product_migration_pack.py plan --backup <folder>
        on :8000, change nothing: every check `apply` makes, then the steps it would run

    python scripts/product_migration_pack.py apply --backup <folder> --confirm-production <database> \\
        --expect-cluster <system identifier> --authorization <decision id>
        on :8000: the same steps as the rehearsal, behind the gates below

`<folder>` is a backup written by `product_backup.ps1` (database.dump, files.tar.gz, manifest.json). The
database is `POSTGRES_RUNTIME_URL`, or `--url`.

The steps are the chain, oldest first, one revision per step and one transaction per step (so a step's lock is
released before the next starts, and a failed step leaves the database at the revision before it). Before each
step, on the step's own connection: the server is the confirmed database in the pinned cluster, an advisory lock
keeps a second migrator out, and the revision is the expected one. After each: the revision is the step's.
`20260924_0016`, the non-additive Reading cutover, is applied by `reading_canonical_cutover.apply`, the reviewed
one-transaction command; legacy Reading rows are renamed into the read-only archive and nothing is converted
(D-143 2).

`apply` refuses unless every one of these holds; nothing is connected to for writing before they all do:

* the backup's files match their recorded sizes and SHA-256, and the backup is younger than `--max-age-hours`;
* `rehearsal.json` beside it passed, was made from this same dump (SHA-256), with this same migration chain
  (digest and head) and with this same migration-execution code (`execution_digest`: the Alembic environment, this
  pack, the cutover and bootstrap commands, the runtime modules they import and the pinned dependencies), and it
  verified table contents: what runs on :8000 is exactly what was rehearsed;
* the server is the database the backup recorded, in the cluster the backup recorded, and both equal
  `--confirm-production` / `--expect-cluster`;
* the database is still at the backup's revision, every table holds exactly the rows the backup counted, and
  every table's content fingerprint (md5 over its rows, over the columns it had at backup time, settings pinned)
  equals the backup's: an UPDATE, or a delete and insert that leave the count unchanged, is seen too. So no write
  happened since the backup, and restoring it loses nothing. (Stop the web and worker first.) A run that stopped
  part-way is resumed by running it again: the revision is then one the chain passes, and counts and fingerprints
  are compared under the renames the applied steps made, over the backup's columns only.
* `--authorization` names the human's decision record, which is printed in the log.

Nothing here prints a secret: URLs are shown with the password redacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "migrations" / "versions"
CUTOVER_REVISION = "20260924_0016"
# What each revision renames, so row counts are compared table for table across it.
RENAMES = {
    CUTOVER_REVISION: {"reading_sessions": "reading_legacy_sessions", "reading_attempts": "reading_legacy_attempts"},
}
# "MPAK" as a 32-bit integer: a second pack run waits on this, on any connection.
_PACK_LOCK = 0x4D50414B
DEFAULT_MAX_AGE_HOURS = 12.0


class Refused(Exception):
    """A gate did not hold; nothing (more) was changed."""


# --- pure checks (no database) ------------------------------------------------------------------------------


def chain_digest(versions: Path = VERSIONS) -> str:
    """SHA-256 over the migration files that make the chain, by name and content (line endings normalised, so a
    Windows checkout and the release artifact agree)."""
    digest = hashlib.sha256()
    for path in sorted(versions.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


# Everything that decides what a migration run does, beyond the revision files themselves: the Alembic
# environment, the commands that drive it, the runtime modules they import, and the pinned dependencies. A
# rehearsal is bound to this exact set (human review 2026-10-08, finding 2).
EXECUTION_SURFACE = (
    "alembic.ini",
    "migrations/env.py",
    "migrations/versions/*.py",
    "scripts/product_migration_pack.py",
    "scripts/reading_canonical_cutover.py",
    "scripts/bootstrap_runtime_schema.py",
    "writing_coach/runtime_schema.py",
    "writing_coach/persistence/runtime.py",
    "writing_coach/persistence/config.py",
    "writing_coach/persistence/models.py",
    "requirements.txt",
)


def execution_files(root: Path = ROOT) -> list[str]:
    """The files of the execution surface, as sorted repository-relative paths."""
    found: set[str] = set()
    for pattern in EXECUTION_SURFACE:
        matches = sorted(root.glob(pattern))
        if not matches:
            raise Refused(f"the execution surface names {pattern}, which this checkout does not have")
        found.update(path.relative_to(root).as_posix() for path in matches)
    return sorted(found)


def execution_digest(root: Path = ROOT) -> str:
    """SHA-256 over every file of the execution surface, by path and content (line endings normalised)."""
    digest = hashlib.sha256()
    for name in execution_files(root):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((root / name).read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(folder: Path) -> dict:
    path = folder / "manifest.json"
    if not path.is_file():
        raise Refused(f"{path} is missing: pass a folder written by product_backup.ps1")
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("format") != "orena-runtime-backup":
        raise Refused(f"{path} is not an orena-runtime-backup manifest")
    return manifest


def check_backup_files(folder: Path, manifest: dict) -> None:
    for entry in manifest.get("files") or []:
        path = folder / entry["name"]
        if not path.is_file():
            raise Refused(f"{entry['name']} is missing from the backup")
        if path.stat().st_size != int(entry["bytes"]) or sha256_file(path) != entry["sha256"]:
            raise Refused(f"{entry['name']} does not match its recorded size and SHA-256")
    if not any(entry.get("name") == "database.dump" for entry in manifest.get("files") or []):
        raise Refused("the manifest records no database.dump")


def dump_sha(manifest: dict) -> str:
    return next(entry["sha256"] for entry in manifest["files"] if entry["name"] == "database.dump")


def backup_age_hours(manifest: dict, now: datetime | None = None) -> float:
    created = datetime.fromisoformat(str(manifest["created_at"]).replace("Z", "+00:00"))
    return ((now or datetime.now(UTC)) - created).total_seconds() / 3600


def check_rehearsal(rehearsal: dict | None, *, manifest: dict, digest: str, head: str, execution: str) -> None:
    if not rehearsal:
        raise Refused("rehearsal.json is missing beside the backup: rehearse this backup first")
    if rehearsal.get("passed") is not True:
        raise Refused("the rehearsal of this backup did not pass")
    if rehearsal.get("dump_sha256") != dump_sha(manifest):
        raise Refused("the rehearsal was made from a different dump than this backup's")
    if rehearsal.get("chain_digest") != digest or rehearsal.get("head") != head:
        raise Refused("the rehearsal ran a different migration chain than this checkout's: rehearse again")
    if rehearsal.get("execution_digest") != execution:
        raise Refused("the rehearsal ran different migration-execution code than this checkout's (pack, cutover, "
                      "Alembic environment, runtime modules or dependencies): rehearse again")
    if rehearsal.get("fingerprints_checked") is not True:
        raise Refused("the rehearsal did not verify table contents (the backup has no content fingerprints): take a "
                      "new backup with product_backup.ps1 and rehearse it")


def renamed(recorded: dict, applied: list[str]) -> dict:
    """A per-table record of the backup under the names the applied revisions gave the tables."""
    values = {table: value for table, value in recorded.items() if table != "alembic_version"}
    for revision in applied:
        for old, new in RENAMES.get(revision, {}).items():
            if old in values:
                values[new] = values.pop(old)
    return values


def fingerprint_differences(expected: dict[str, str], found: dict[str, str]) -> list[str]:
    """Tables whose content is not what the backup recorded (same columns, any row inserted, deleted or changed)."""
    return sorted(table for table, value in expected.items() if found.get(table) != value)


def expected_counts(recorded: dict[str, int], applied: list[str]) -> dict[str, int]:
    """The backup's row counts under the names the applied revisions gave the tables."""
    return renamed(recorded, applied)


def count_differences(expected: dict[str, int], found: dict[str, int]) -> list[str]:
    return [f"{table}: backup {count}, now {found.get(table, 'absent')}"
            for table, count in sorted(expected.items()) if found.get(table) != count]


# --- database ---------------------------------------------------------------------------------------------


def _engine(url: str):
    from sqlalchemy import create_engine

    return create_engine(url, future=True)


def _pending(actual: str | None, head: str) -> list[str]:
    from scripts.bootstrap_runtime_schema import pending_revisions

    return pending_revisions(actual, head)


def _chain() -> list[str]:
    return _pending(None, _head())


def _head() -> str:
    from writing_coach.persistence.runtime import runtime_head

    return runtime_head()


def table_counts(connection) -> dict[str, int]:
    from sqlalchemy import inspect, text

    names = inspect(connection).get_table_names()
    return {name: int(connection.execute(text(f'SELECT count(*) FROM "{name}"')).scalar_one())
            for name in sorted(names) if name != "alembic_version"}


# The session settings every content fingerprint is computed under, here and in product_backup.ps1, so a value
# renders as the same text wherever it is read (a timestamptz depends on TimeZone, a date on DateStyle).
FINGERPRINT_SETTINGS = (
    "SET LOCAL TimeZone = 'UTC'",
    "SET LOCAL DateStyle = 'ISO, MDY'",
    "SET LOCAL IntervalStyle = 'postgres'",
    "SET LOCAL extra_float_digits = 1",
    "SET LOCAL bytea_output = 'hex'",
)


def _identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def fingerprint_sql(table: str, columns: list[str]) -> str:
    """md5 over the sorted md5 of each row, the row being exactly the given columns in the given order. The same
    expression product_backup.ps1 builds for every table at backup time."""
    row = ", ".join(f"t.{_identifier(column)}" for column in columns)
    return (f"SELECT md5(coalesce(string_agg(h, '' ORDER BY h), '')) FROM "
            f"(SELECT md5(ROW({row})::text) AS h FROM public.{_identifier(table)} t) s")


def table_fingerprints(connection, columns: dict[str, list[str]]) -> dict[str, str]:
    """The content fingerprint of each table that exists, over the columns the backup recorded for it."""
    from sqlalchemy import inspect, text

    present = set(inspect(connection).get_table_names())
    for setting in FINGERPRINT_SETTINGS:
        connection.execute(text(setting))
    return {table: str(connection.execute(text(fingerprint_sql(table, cols))).scalar_one())
            for table, cols in sorted(columns.items()) if table in present and cols}


def revision_on(connection) -> str | None:
    from alembic.runtime.migration import MigrationContext

    return MigrationContext.configure(connection).get_current_revision()


def applied_since(start: str | None, actual: str | None) -> list[str]:
    """The chain's revisions after `start` up to and including `actual` (both in the chain)."""
    chain = _chain()
    first = chain.index(start) + 1 if start else 0
    return chain[first:chain.index(actual) + 1] if actual else []


def check_state(connection, *, manifest: dict) -> tuple[str | None, list[str], bool]:
    """The database is at the backup's revision, or one the chain reaches from it, and holds exactly the rows the
    backup counted and, when the backup recorded them, exactly the contents. Returns (revision, steps still to run,
    whether contents were checked)."""
    head = _head()
    start = manifest.get("schema_revision") or None
    actual = revision_on(connection)
    chain = _chain()
    if start and start not in chain:
        raise Refused(f"the backup is at {start}, which this chain does not know")
    if actual != start and (actual not in chain or (start and chain.index(actual) < chain.index(start))):
        raise Refused(f"the database is at {actual or 'no revision'}, not the backup's {start} or a revision after it")
    expected = expected_counts({k: int(v) for k, v in (manifest.get("table_counts") or {}).items()},
                               applied_since(start, actual))
    found = table_counts(connection)
    differences = count_differences(expected, found)
    if differences:
        raise Refused("rows changed since the backup (stop the web and worker, take a new backup): "
                      + "; ".join(differences[:8]) + (" ..." if len(differences) > 8 else ""))
    # Row counts miss an UPDATE, or a delete and an insert that cancel out. The content fingerprint of every table,
    # over the columns it had at backup time, does not (human review 2026-10-08, finding 1).
    checked = False
    recorded, columns = manifest.get("table_fingerprints"), manifest.get("table_columns")
    if recorded and columns:
        # PowerShell may write a one-column list as a bare string.
        columns = {table: cols.split(",") if isinstance(cols, str) else list(cols) for table, cols in columns.items()}
        applied = applied_since(start, actual)
        changed = fingerprint_differences(renamed(recorded, applied),
                                          table_fingerprints(connection, renamed(columns, applied)))
        if changed:
            raise Refused("table contents changed since the backup although row counts did not (stop the web and "
                          "worker, take a new backup): " + ", ".join(changed[:8]) + (" ..." if len(changed) > 8 else ""))
        checked = True
    return actual, ([] if actual == head else _pending(actual, head)), checked


def step(url: str, *, revision: str, before: str | None, database: str, cluster: str) -> float:
    """Apply one revision, gated and in one transaction. Returns seconds."""
    from alembic import command
    from sqlalchemy import text

    from scripts import reading_canonical_cutover as cutover
    from writing_coach.persistence.runtime import _runtime_alembic_config

    started = time.monotonic()
    if revision == CUTOVER_REVISION:
        if cutover.apply(url, confirmed=database, expect_cluster=cluster, from_revision=before or "") != 0:
            raise Refused(f"{revision}: the Reading cutover refused or failed; the database is at {before}")
        return time.monotonic() - started
    engine = _engine(url)
    try:
        with engine.begin() as connection:
            reason = cutover.identity_refusal(cutover.identity_on(connection), confirmed=database,
                                              expect_cluster=cluster)
            if reason:
                raise Refused(reason)
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _PACK_LOCK})
            if revision_on(connection) != before:
                raise Refused(f"{revision}: the database is at {revision_on(connection)}, not {before}")
            config = _runtime_alembic_config()
            config.attributes["connection"] = connection
            command.upgrade(config, revision)
            if revision_on(connection) != revision:
                raise Refused(f"{revision}: the upgrade ended at {revision_on(connection)}; rolled back")
    finally:
        engine.dispose()
    return time.monotonic() - started


def verify_after(url: str, *, manifest: dict) -> dict:
    """At head, ready, every backed-up row where its table now lives, legacy Reading archive frozen."""
    from writing_coach.runtime_schema import READY, readiness

    engine = _engine(url)
    try:
        with engine.connect() as connection:
            actual = revision_on(connection)
            found = table_counts(connection)
            from sqlalchemy import text

            triggers = 0
            if {"reading_legacy_sessions", "reading_legacy_attempts"} <= set(found):
                triggers = int(connection.execute(text(
                    "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid WHERE NOT t.tgisinternal "
                    "AND c.relname IN ('reading_legacy_sessions', 'reading_legacy_attempts')")).scalar_one())
    finally:
        engine.dispose()
    head = _head()
    expected = expected_counts({k: int(v) for k, v in (manifest.get("table_counts") or {}).items()},
                               applied_since(manifest.get("schema_revision") or None, actual))
    differences = count_differences(expected, found)
    state = readiness(actual=actual, tables=set(found) | {"alembic_version"}, expected=head)
    legacy_archived = "reading_legacy_sessions" in found
    return {
        "revision": actual,
        "ready": state == READY,
        "rows_kept": not differences,
        "row_differences": differences,
        "new_tables": sorted(set(found) - set(expected)),
        "legacy_reading": {"sessions": found.get("reading_legacy_sessions"),
                           "attempts": found.get("reading_legacy_attempts"),
                           "freeze_triggers": triggers} if legacy_archived else None,
        "legacy_frozen": (not legacy_archived) or triggers > 0,
    }


def identity(url: str) -> dict[str, str]:
    from scripts import reading_canonical_cutover as cutover

    return cutover.identity(url)


def run_chain(url: str, *, manifest: dict, database: str, cluster: str, log) -> dict:
    engine = _engine(url)
    try:
        with engine.connect() as connection:
            actual, steps, checked = check_state(connection, manifest=manifest)
    finally:
        engine.dispose()
    log(f"rows {'and contents ' if checked else ''}match the backup"
        f"{'' if checked else ' (this backup records no content fingerprints)'}")
    log(f"database {database} in cluster {cluster} is at {actual or 'no revision'}; "
        f"{len(steps)} step(s) to {_head()}: {' '.join(steps) or 'none'}")
    timings = []
    before = actual
    for revision in steps:
        seconds = step(url, revision=revision, before=before, database=database, cluster=cluster)
        timings.append({"revision": revision, "seconds": round(seconds, 3)})
        log(f"  {revision}  {seconds:8.2f} s")
        before = revision
    result = verify_after(url, manifest=manifest)
    result["steps"] = timings
    result["started_from"] = actual
    result["fingerprints_checked"] = checked
    return result


# --- commands ---------------------------------------------------------------------------------------------


def _log(message: str) -> None:
    print(message, flush=True)


def cmd_digest() -> int:
    print(f"HEAD={_head()}")
    print(f"DIGEST={chain_digest()}")
    print(f"EXECUTION={execution_digest()}")
    return 0


def cmd_rehearse(url: str, folder: Path, confirmed: str) -> int:
    from scripts import reading_canonical_cutover as cutover

    manifest = load_manifest(folder)
    check_backup_files(folder, manifest)
    found = identity(url)
    if found["database"] != confirmed:
        raise Refused(f"connected to {found['database']!r}, not the confirmed {confirmed!r}")
    # A restored copy is a different cluster from the one it was dumped from. The same cluster means this is the
    # source itself, which a rehearsal never touches.
    if not found["cluster"]:
        raise Refused("this role cannot read the cluster's system identifier")
    if manifest.get("cluster") and found["cluster"] == str(manifest["cluster"]):
        raise Refused("this is the cluster the backup was taken from, not a restored copy: nothing was touched")
    reason = cutover.refusal(url=url, app_url="", environ=dict(os.environ), confirmed=confirmed)
    if reason:
        raise Refused(reason)
    result = run_chain(url, manifest=manifest, database=found["database"], cluster=found["cluster"], log=_log)
    report = {
        "format": "orena-migration-rehearsal", "version": 3,
        "finished_at": datetime.now(UTC).isoformat(),
        "dump_sha256": dump_sha(manifest), "backup_revision": manifest.get("schema_revision"),
        "head": _head(), "chain_digest": chain_digest(),
        "execution_digest": execution_digest(), "execution_files": execution_files(),
        **result,
    }
    report["passed"] = bool(result["ready"] and result["rows_kept"] and result["legacy_frozen"])
    print("REPORT=" + json.dumps(report, separators=(",", ":")))
    return 0 if report["passed"] else 1


def production_checks(url: str, folder: Path, *, confirmed: str, cluster: str, max_age: float) -> tuple[dict, dict]:
    manifest = load_manifest(folder)
    check_backup_files(folder, manifest)
    age = backup_age_hours(manifest)
    if age > max_age:
        raise Refused(f"the backup is {age:.1f} h old (limit {max_age} h): take a fresh one and rehearse it")
    rehearsal_path = folder / "rehearsal.json"
    rehearsal = json.loads(rehearsal_path.read_text(encoding="utf-8-sig")) if rehearsal_path.is_file() else None
    if not manifest.get("table_fingerprints") or not manifest.get("table_columns"):
        raise Refused("the backup records no content fingerprints, so a write since it could go unseen: take it "
                      "again with product_backup.ps1 (manifest version 3) and rehearse it")
    check_rehearsal(rehearsal, manifest=manifest, digest=chain_digest(), head=_head(), execution=execution_digest())
    if manifest.get("database") != confirmed:
        raise Refused(f"--confirm-production {confirmed!r} is not the backup's database {manifest.get('database')!r}")
    if not manifest.get("cluster") or str(manifest["cluster"]) != cluster.strip():
        raise Refused("--expect-cluster is not the cluster the backup recorded (re-take the backup with "
                      "product_backup.ps1, which records it)")
    found = identity(url)
    if found["database"] != confirmed or found["cluster"] != cluster.strip():
        raise Refused(f"connected to database {found['database']!r} in cluster {found['cluster'] or '?'}, not the "
                      "backup's: nothing was touched")
    return manifest, found


def cmd_plan(url: str, folder: Path, max_age: float) -> int:
    manifest = load_manifest(folder)
    confirmed, cluster = str(manifest.get("database") or ""), str(manifest.get("cluster") or "")
    manifest, found = production_checks(url, folder, confirmed=confirmed, cluster=cluster, max_age=max_age)
    engine = _engine(url)
    try:
        with engine.connect() as connection:
            actual, steps, _ = check_state(connection, manifest=manifest)
    finally:
        engine.dispose()
    print(f"database {found['database']} cluster {found['cluster']} at {actual}; rehearsed chain matches")
    for revision in steps:
        print(f"step: {revision}{'  (Reading cutover, reading_canonical_cutover.apply)' if revision == CUTOVER_REVISION else ''}")
    print(f"plan: {len(steps)} step(s); nothing was changed")
    return 0


def cmd_apply(url: str, folder: Path, *, confirmed: str, cluster: str, authorization: str, max_age: float) -> int:
    if not authorization.strip():
        raise Refused("--authorization must name the human's decision record for this apply")
    manifest, found = production_checks(url, folder, confirmed=confirmed, cluster=cluster, max_age=max_age)
    _log(f"authorization: {authorization.strip()}")
    result = run_chain(url, manifest=manifest, database=found["database"], cluster=found["cluster"], log=_log)
    result["authorization"] = authorization.strip()
    result["finished_at"] = datetime.now(UTC).isoformat()
    print("RESULT=" + json.dumps(result, separators=(",", ":")))
    return 0 if result["ready"] and result["rows_kept"] and result["legacy_frozen"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("command", choices=("digest", "rehearse", "plan", "apply"))
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL")
    parser.add_argument("--confirm-rehearsal", default="", metavar="DATABASE")
    parser.add_argument("--confirm-production", default="", metavar="DATABASE")
    parser.add_argument("--expect-cluster", default="", metavar="SYSTEM_IDENTIFIER")
    parser.add_argument("--authorization", default="", metavar="DECISION")
    parser.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS)
    args = parser.parse_args(argv)
    if args.command == "digest":
        return cmd_digest()
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    try:
        if not url:
            raise Refused("no database: pass --url or set POSTGRES_RUNTIME_URL")
        if args.backup is None:
            raise Refused(f"{args.command} needs --backup <folder from product_backup.ps1>")
        if args.command == "rehearse":
            if not args.confirm_rehearsal:
                raise Refused("rehearse needs --confirm-rehearsal <database of the restored copy>")
            return cmd_rehearse(url, args.backup, args.confirm_rehearsal)
        if args.command == "plan":
            return cmd_plan(url, args.backup, args.max_age_hours)
        if not args.confirm_production or not args.expect_cluster:
            raise Refused("apply needs --confirm-production <database> and --expect-cluster <system identifier>")
        return cmd_apply(url, args.backup, confirmed=args.confirm_production, cluster=args.expect_cluster,
                         authorization=args.authorization, max_age=args.max_age_hours)
    except Refused as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
