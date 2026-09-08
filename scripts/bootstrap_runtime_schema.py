"""Create the runtime schema. The only thing that does.

Startup verifies and refuses; this applies the migrations, and it applies them
because an operator ran it and said so. It reports what it found before doing
anything, and it will not touch a database that already has something in it.

    python scripts/bootstrap_runtime_schema.py            # report only
    python scripts/bootstrap_runtime_schema.py --confirm  # apply

Existing operator tooling is unchanged: `scripts/postgres_shadow.py` still
builds a shadow database, and the cutover rehearsal still verifies the head.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import command  # noqa: E402

from writing_coach.persistence.config import create_runtime_engine  # noqa: E402
from writing_coach.persistence.runtime import (  # noqa: E402
    _read_runtime_state,
    _runtime_alembic_config,
    runtime_head,
)
from writing_coach.runtime_schema import (  # noqa: E402
    EMPTY,
    READY,
    UNAVAILABLE,
    describe_readiness,
    readiness,
)


def inspect_runtime() -> tuple[str, str, str | None]:
    """(state, expected revision, actual revision) for the configured runtime."""
    expected = runtime_head()
    try:
        actual, tables = _read_runtime_state(create_runtime_engine())
    except Exception:
        return UNAVAILABLE, expected, None
    return readiness(actual=actual, tables=tables, expected=expected), expected, actual


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="apply the migrations; without it this only reports what it found",
    )
    args = parser.parse_args(argv)

    state, expected, actual = inspect_runtime()
    print(f"runtime schema: {state} (expected {expected}, found {actual or 'no revision'})")

    if state == READY:
        print("Nothing to do.")
        return 0
    if state != EMPTY:
        # A database with tables in it, or one that cannot be read, is not
        # something to migrate on a hunch.
        print(describe_readiness(state, expected=expected, actual=actual), file=sys.stderr)
        return 1
    if not args.confirm:
        print("Empty database. Re-run with --confirm to create the schema.")
        return 2

    command.upgrade(_runtime_alembic_config(include_runtime_url=True), "head")
    state, expected, actual = inspect_runtime()
    print(f"after migration: {state} (expected {expected}, found {actual or 'no revision'})")
    return 0 if state == READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
