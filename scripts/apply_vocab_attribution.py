"""Set the CC-CEDICT licence and attribution on vocabulary collections built with it.

Dry run by default: lists the collections and whether each would change. `--apply` writes
only `provenance.licence`, idempotently, and never changes status or any other key.

    python scripts/apply_vocab_attribution.py                       # dry run, collections naming CC-CEDICT
    python scripts/apply_vocab_attribution.py --id pilot-zh-idioms  # explicit ids (repeatable)
    python scripts/apply_vocab_attribution.py --apply

Run inside the application container against POSTGRES_RUNTIME_URL (or `--url`; never printed).
Exit status: 0 done / nothing to do, 2 no usable database.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine  # noqa: E402

from writing_coach import vocabulary_attribution  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    parser.add_argument("--id", action="append", dest="ids", help="collection id (repeatable)")
    parser.add_argument("--apply", action="store_true", help="write; without it nothing changes")
    args = parser.parse_args(argv)
    url = args.url or os.getenv("POSTGRES_RUNTIME_URL", "")
    if not url:
        print("refused: no database: pass --url or set POSTGRES_RUNTIME_URL")
        return 2
    try:
        engine = create_engine(url)
        rows = (vocabulary_attribution.apply if args.apply else vocabulary_attribution.plan)(engine, args.ids)
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never the URL
        print(f"refused: could not update the vocabulary collections ({type(exc).__name__})")
        return 2
    verb = "updated" if args.apply else "would update"
    for row in rows:
        print(f"- {row['id']}  status={row['status']}  {verb if row['change'] else 'already set'}")
    print(f"{sum(r['change'] for r in rows)} of {len(rows)} collection(s) {verb}." + ("" if args.apply else " (dry run)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
