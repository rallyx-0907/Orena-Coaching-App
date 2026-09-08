"""Create or migrate the runtime schema. The only thing that does.

Startup verifies and refuses; this applies migrations, and it applies them
because an operator ran it and said so. It reports what it found before doing
anything.

    python scripts/bootstrap_runtime_schema.py
        report only, always safe

    python scripts/bootstrap_runtime_schema.py --confirm
        create the schema in an EMPTY database

    python scripts/bootstrap_runtime_schema.py --upgrade --from <revision> --confirm
        migrate a database that already has data

The two modes are separate on purpose. Creating a schema where none exists and
migrating a database with a learner's work in it are different risks, and the
second one asks the operator to state which revision they believe the database
is at. If it is at a different one, the command stops - that mismatch usually
means the connection string points somewhere unexpected, which is exactly the
moment not to run a migration.

Take a verified backup before `--upgrade`. See
`docs/project/I2_ACTIVATION_RUNBOOK.md`; `scripts/runtime_backup.py` is the
procedure, and its restore rehearsal is part of the checklist.

Existing operator tooling is unchanged: `scripts/postgres_shadow.py` still
builds a shadow database, and the cutover rehearsal still verifies the head.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Only the pure state vocabulary is imported at module load. Alembic,
# SQLAlchemy and a database connection are reached for when something is
# actually done, so the command's argument rules can be exercised anywhere and
# a missing driver is a use-time failure rather than an import-time one.
from writing_coach.runtime_schema import (  # noqa: E402
    EMPTY,
    MISMATCH,
    READY,
    UNAVAILABLE,
    describe_readiness,
    readiness,
)


def inspect_runtime() -> tuple[str, str, str | None]:
    """(state, expected revision, actual revision) for the configured runtime."""
    from writing_coach.persistence.config import create_runtime_engine
    from writing_coach.persistence.runtime import _read_runtime_state, runtime_head

    expected = runtime_head()
    try:
        actual, tables = _read_runtime_state(create_runtime_engine())
    except Exception:
        return UNAVAILABLE, expected, None
    return readiness(actual=actual, tables=tables, expected=expected), expected, actual


def _apply(label: str) -> int:
    from alembic import command

    from writing_coach.persistence.runtime import _runtime_alembic_config

    command.upgrade(_runtime_alembic_config(include_runtime_url=True), "head")
    state, expected, actual = inspect_runtime()
    print(f"after {label}: {state} (expected {expected}, found {actual or 'no revision'})")
    return 0 if state == READY else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="apply; without it this only reports what it found",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="migrate a database that already has data, rather than create one",
    )
    parser.add_argument(
        "--from",
        dest="from_revision",
        default="",
        help="the revision you believe this database is at; required with --upgrade",
    )
    args = parser.parse_args(argv)

    state, expected, actual = inspect_runtime()
    print(f"runtime schema: {state} (expected {expected}, found {actual or 'no revision'})")

    if state == READY:
        print("Nothing to do.")
        return 0
    if state == UNAVAILABLE:
        print(describe_readiness(state, expected=expected, actual=actual), file=sys.stderr)
        return 1

    if args.upgrade:
        if state != MISMATCH:
            print(
                "--upgrade migrates a database that already has data. This one is "
                f"{state}; use --confirm on its own to create a schema.",
                file=sys.stderr,
            )
            return 1
        if not args.from_revision:
            print(
                "--upgrade requires --from <revision>: state which revision you "
                "believe this database is at, so a connection string pointing "
                "somewhere unexpected stops here rather than being migrated.",
                file=sys.stderr,
            )
            return 1
        if args.from_revision != (actual or ""):
            print(
                f"This database is at {actual or 'no revision'}, not "
                f"{args.from_revision}. Check which database this is pointed at.",
                file=sys.stderr,
            )
            return 1
        if not args.confirm:
            print(
                f"Ready to migrate {actual} -> {expected}. Take a verified backup "
                "first, then re-run with --confirm."
            )
            return 2
        return _apply("migration")

    if state != EMPTY:
        # A database with tables in it is not migrated on a hunch; that is what
        # --upgrade is for, and it asks which revision the operator expects.
        print(describe_readiness(state, expected=expected, actual=actual), file=sys.stderr)
        print(
            "To migrate an existing database, use: --upgrade --from "
            f"{actual or '<revision>'} --confirm",
            file=sys.stderr,
        )
        return 1
    if not args.confirm:
        print("Empty database. Re-run with --confirm to create the schema.")
        return 2
    return _apply("creation")


if __name__ == "__main__":
    raise SystemExit(main())
