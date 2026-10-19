"""Dry run of the Orena Memory retention sweep (PRE-503): how many expired rows the daily sweep would delete now.

Reads only, in a READ ONLY transaction: no row is deleted, locked or changed, and no memory text is read. Run it in
the application image against the database the sweep would run on, before the owner switches
AGENT_MEMORY_RETENTION_SWEEP on:

    python -m scripts.memory_retention_dry_run            # uses POSTGRES_RUNTIME_URL
    python -m scripts.memory_retention_dry_run --url URL  # or an explicit URL (never printed - but it stays in the
                                                          # shell history and process list: prefer the variable)
    python -m scripts.memory_retention_dry_run --at 2026-12-01T00:00:00+00:00   # as of another moment

Prints one JSON object: the moment, and the counts by table (memories by class; a class with none is absent).
One daily sweep removes at most MAX_BATCHES x BATCH rows per table per process (ExpiredMemorySweep): a larger backlog
takes more than one day. A future --at overstates what will go: notes in use are renewed (PRE-005 v2).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=None, help="database URL; default POSTGRES_RUNTIME_URL")
    parser.add_argument("--at", default=None, help="ISO moment to count as of; default now (UTC)")
    args = parser.parse_args(argv)
    url = args.url or os.environ.get("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("no database URL: set POSTGRES_RUNTIME_URL or pass --url", file=sys.stderr)
        return 2
    try:
        at = datetime.fromisoformat(args.at) if args.at else datetime.now(UTC)
    except ValueError:
        print("--at is not an ISO date-time (e.g. 2026-12-01T00:00:00+00:00)", file=sys.stderr)
        return 2
    if at.tzinfo is None:
        print("--at needs a timezone (e.g. +00:00)", file=sys.stderr)
        return 2
    import sqlalchemy

    from writing_coach.persistence.memory_repository import count_expired

    engine = sqlalchemy.create_engine(url, future=True)
    try:
        counts = count_expired(engine, at)
    finally:
        engine.dispose()
    print(json.dumps({"at": at.isoformat(), "would_delete": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
