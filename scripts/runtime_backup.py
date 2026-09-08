"""Take and verify a runtime backup, and rehearse restoring it.

A backup nobody has restored is a hope, not a backup. So this has three modes
and the middle one is not optional in the checklist:

    python scripts/runtime_backup.py capture --out backups/pre-i2.dump
    python scripts/runtime_backup.py rehearse --dump backups/pre-i2.dump \\
        --into orena_restore_rehearsal
    python scripts/runtime_backup.py verify --dump backups/pre-i2.dump

`capture` writes a custom-format `pg_dump`. `rehearse` restores it into a
*separate* database and compares revision and row counts against the source -
never over the runtime database, which this script has no mode for touching.
`verify` re-reads a dump's own listing without a server.

Backups are access-controlled operational copies and are never account sync
authority: restoring one reinstates a database, and the deletion records inside
it still apply before anything is served. That rule belongs to the account
architecture; this script only makes the copy and proves it can come back.

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
from pathlib import Path
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


def capture(url: str, out: Path) -> int:
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


def rehearse(url: str, dump: Path, into: str) -> int:
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
    parser.add_argument("mode", choices=("capture", "verify", "rehearse"))
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL")
    parser.add_argument("--out", type=Path, help="capture: where to write the dump")
    parser.add_argument("--dump", type=Path, help="verify/rehearse: the dump to read")
    parser.add_argument("--into", default="", help="rehearse: the database to restore into")
    args = parser.parse_args(argv)

    if args.mode == "verify":
        return verify(args.dump) if args.dump else 1

    from writing_coach.persistence.config import runtime_url

    url = args.url or runtime_url()
    if args.mode == "capture":
        return capture(url, args.out) if args.out else 1
    if not args.dump or not args.into:
        print("rehearse needs --dump and --into", file=sys.stderr)
        return 1
    return rehearse(url, args.dump, args.into)


if __name__ == "__main__":
    raise SystemExit(main())
