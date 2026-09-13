"""Take and verify a runtime backup, and rehearse restoring it.

A backup nobody has restored is a hope, not a backup. So this has three modes
and the middle one is not optional in the checklist:

    python scripts/runtime_backup.py capture --out backups/pre-i2.dump
    python scripts/runtime_backup.py rehearse --dump backups/pre-i2.dump \\
        --into orena_restore_rehearsal
    python scripts/runtime_backup.py verify --dump backups/pre-i2.dump

and two more for the one thing a restore must never undo - a deletion (D-054):

    python scripts/runtime_backup.py deletions --out backups/deletions.json
    python scripts/runtime_backup.py suppress --into orena_restored \\
        --deletions backups/deletions.json

`deletions` exports every deleted incarnation from the database being
replaced into a journal that lives outside any database. `suppress` marks each
of them deleted again in the restored database, in one transaction, before it
is served. `rehearse --deletions FILE` does the same inside a rehearsal.

`capture` writes a custom-format `pg_dump`. `rehearse` restores it into a
*separate* database and compares revision and row counts against the source -
never over the runtime database, which this script has no mode for touching.
`verify` re-reads a dump's own listing without a server.

Backups are access-controlled operational copies and are never account sync
authority. Deleting an account is permanent (D-054), so restoring one
reinstates a database *and then* the deletions made since it was taken: the
restore is not served until `suppress` has run. The journal holds opaque ids
and times, no content, and is kept with the same access control as backups.

Requires `pg_dump`, `pg_restore` and `psql` on PATH. **The application image
does not ship them** - it is a Debian base without `postgresql-client` - so
this runs from an operator environment that has the client tools, or from an
ephemeral container with them installed. The runbook says which; the script
says so too rather than failing with a traceback.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Directories that do not outlive the container they are written in. This
# script is normally run from an ephemeral `docker run --rm`, because the
# application image has no postgresql-client - so a dump written to one of
# these is captured, verified, rehearsed, and then gone the moment the
# container exits. That is not hypothetical: it is how a real pre-migration
# backup was lost.
EPHEMERAL_ROOTS = ('/tmp', '/var/tmp', '/dev/shm')


def ephemeral_reason(out: Path) -> str | None:
    """Why this destination will not survive, or None if it will."""
    candidate = PurePosixPath(Path(out).as_posix())
    if not candidate.is_absolute():
        return None
    for root in EPHEMERAL_ROOTS:
        base = PurePosixPath(root)
        if candidate == base or base in candidate.parents:
            return (
                f"{out} is under {root}, which does not outlive the container "
                "this usually runs in - the dump would pass every check and "
                "then disappear. Write it to a mounted path instead (the "
                "repository's backups/ directory is the default). Pass "
                "--allow-ephemeral only when the dump is genuinely being "
                "copied out before the container exits."
            )
    return None


def default_out(at: str | None = None) -> Path:
    """A durable, non-colliding destination, so the operator need not choose.

    Timestamped rather than fixed: overwriting the previous backup with the
    current one is its own way of having no backup.
    """
    stamp = at or datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    return Path(__file__).resolve().parents[1] / 'backups' / f'orena-{stamp}.dump'

# The tables whose row counts a rehearsal compares. Domain-owned evidence and
# the account rows that scope it: if these come back, the restore is real.
COMPARED = (
    "users",
    "user_language_profiles",
    "essays",
    "essay_revisions",
    "saved_words",
    "speaking_attempts",
    "listening_progress",
    "shadowing_progress",
)


def _libpq_url(url: str) -> str:
    """SQLAlchemy's `postgresql+psycopg://` is not what pg_dump accepts."""
    parsed = urlparse(url)
    scheme = parsed.scheme.split("+", 1)[0] or "postgresql"
    return urlunparse(parsed._replace(scheme=scheme))


def _require_client_tools(*names: str) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise SystemExit(
            f"{', '.join(missing)} not found on PATH. The application image does "
            "not ship postgresql-client; run this from an operator environment "
            "that has it, or install it into an ephemeral container first. See "
            "docs/project/I2_ACTIVATION_RUNBOOK.md."
        )


def _run(argv: list[str]) -> subprocess.CompletedProcess:
    print("$", " ".join(argv))
    return subprocess.run(argv, check=False, capture_output=True, text=True)


def capture(url: str, out: Path, allow_ephemeral: bool = False) -> int:
    # Checked before pg_dump runs: a backup that lands nowhere is worse than
    # one that was never attempted, because it looks like it worked.
    if not allow_ephemeral:
        reason = ephemeral_reason(out)
        if reason:
            raise SystemExit(reason)
    _require_client_tools("pg_dump")
    out.parent.mkdir(parents=True, exist_ok=True)
    result = _run(["pg_dump", "--format=custom", "--file", str(out), _libpq_url(url)])
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return 1
    size = out.stat().st_size
    print(f"captured {out} ({size} bytes)")
    # An empty file is a failure that returned zero often enough to be worth
    # checking for.
    return 0 if size > 0 else 1


def verify(dump: Path) -> int:
    _require_client_tools("pg_restore")
    if not dump.exists():
        print(f"no such dump: {dump}", file=sys.stderr)
        return 1
    result = _run(["pg_restore", "--list", str(dump)])
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return 1
    entries = [line for line in result.stdout.splitlines() if line and not line.startswith(";")]
    print(f"{dump} lists {len(entries)} restorable entries")
    return 0 if entries else 1


def _counts(url: str, database: str) -> dict[str, int | None]:
    from sqlalchemy import create_engine, text

    parsed = urlparse(url)
    engine = create_engine(urlunparse(parsed._replace(path=f"/{database}")), future=True)
    counts: dict[str, int | None] = {}
    with engine.connect() as connection:
        for table in ("alembic_version", *COMPARED):
            try:
                if table == "alembic_version":
                    counts[table] = connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one_or_none()
                else:
                    counts[table] = connection.execute(
                        text(f"SELECT count(*) FROM {table}")  # noqa: S608 - fixed list
                    ).scalar_one()
            except Exception:
                counts[table] = None
    engine.dispose()
    return counts


def _engine_for(url: str, database: str):
    from sqlalchemy import create_engine

    parsed = urlparse(url)
    return create_engine(urlunparse(parsed._replace(path=f"/{database}")), future=True)


def export_journal(url: str, out: Path) -> int:
    from writing_coach.persistence.deletion_journal import export_deletions, write_journal

    engine = create_engine_for_url(url)
    try:
        body = export_deletions(engine)
    finally:
        engine.dispose()
    write_journal(out, body)
    print(f"exported {len(body['records'])} deleted incarnation(s) to {out}")
    return 0


def create_engine_for_url(url: str):
    from sqlalchemy import create_engine

    return create_engine(url, future=True)


def suppress(url: str, into: str, journals: list[Path]) -> int:
    """Reapply deletions to a restored database before it serves."""
    from writing_coach.persistence.deletion_journal import (
        JournalInvalid, merge, read_journal, reapply_deletions,
    )

    if not journals:
        print("suppress needs at least one --deletions journal", file=sys.stderr)
        return 1
    try:
        body = merge(*(read_journal(path) for path in journals))
    except JournalInvalid as error:
        print(f"refusing: {error}", file=sys.stderr)
        return 1
    engine = _engine_for(url, into)
    try:
        summary = reapply_deletions(engine, body)
    except JournalInvalid as error:
        print(f"refusing: {error}; nothing was changed", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(
        f"deletions reapplied to {into}: {summary['reapplied']} reapplied, "
        f"{summary['already_deleted']} already deleted, {summary['absent']} absent (created after the backup)"
    )
    return 0


def rehearse(url: str, dump: Path, into: str, journals: list[Path] | None = None) -> int:
    """Restore into a separate database and compare it with the source.

    The target is created and dropped here. It is never the runtime database:
    the source name and the target name must differ, and this refuses if they
    do not.
    """
    _require_client_tools("pg_restore", "psql")
    parsed = urlparse(url)
    source = parsed.path.lstrip("/")
    if into == source:
        print(
            f"refusing to restore over the source database {source!r}; "
            "a rehearsal restores somewhere else",
            file=sys.stderr,
        )
        return 1

    admin = _libpq_url(urlunparse(parsed._replace(path="/postgres")))
    for statement in (f'DROP DATABASE IF EXISTS "{into}"', f'CREATE DATABASE "{into}"'):
        result = _run(["psql", "-v", "ON_ERROR_STOP=1", "-c", statement, admin])
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            return 1

    target = _libpq_url(urlunparse(parsed._replace(path=f"/{into}")))
    result = _run(["pg_restore", "--no-owner", "--dbname", target, str(dump)])
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        return 1

    if journals and suppress(url, into, journals) != 0:
        _run(["psql", "-v", "ON_ERROR_STOP=1", "-c", f'DROP DATABASE IF EXISTS "{into}"', admin])
        return 1

    before, after = _counts(url, source), _counts(url, into)
    print(f"{'table':<26}{'source':>12}{'restored':>12}")
    mismatched = []
    for table, value in before.items():
        restored = after.get(table)
        print(f"{table:<26}{str(value):>12}{str(restored):>12}")
        if value != restored:
            mismatched.append(table)

    _run(["psql", "-v", "ON_ERROR_STOP=1", "-c", f'DROP DATABASE IF EXISTS "{into}"', admin])
    if mismatched:
        print(f"restore did not match on: {', '.join(mismatched)}", file=sys.stderr)
        return 1
    print("restore rehearsal matched the source on revision and every compared count")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "verify", "rehearse", "deletions", "suppress"))
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL")
    parser.add_argument("--out", type=Path,
                        help="capture: where to write the dump (default: backups/)")
    parser.add_argument("--dump", type=Path, help="verify/rehearse: the dump to read")
    parser.add_argument("--into", default="", help="rehearse/suppress: the restored database")
    parser.add_argument("--deletions", type=Path, action="append", default=[],
                        help="suppress/rehearse: a deletion journal (repeatable)")
    parser.add_argument("--allow-ephemeral", action="store_true",
                        help="capture: permit a destination that dies with its container")
    args = parser.parse_args(argv)

    if args.mode == "verify":
        return verify(args.dump) if args.dump else 1

    from writing_coach.persistence.config import runtime_url

    url = args.url or runtime_url()
    if args.mode == "capture":
        return capture(url, args.out or default_out(), args.allow_ephemeral)
    if args.mode == "deletions":
        if not args.out:
            print("deletions needs --out", file=sys.stderr)
            return 1
        return export_journal(url, args.out)
    if args.mode == "suppress":
        if not args.into:
            print("suppress needs --into", file=sys.stderr)
            return 1
        return suppress(url, args.into, args.deletions)
    if not args.dump or not args.into:
        print("rehearse needs --dump and --into", file=sys.stderr)
        return 1
    return rehearse(url, args.dump, args.into, args.deletions)


if __name__ == "__main__":
    raise SystemExit(main())
