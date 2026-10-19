"""Give every published item that has no thumbnail Orena's typographic cover (D-240, source 3).

Dry run by default: it prints what it would add and changes nothing. `--apply` writes the covers (SVG, made from the
title, language and topic with the design tokens only - no AI, no network, $0) into the runtime asset roots and records
them with their provenance. An item that already has any thumbnail is never touched. Nothing is unpublished.

    python scripts/backfill_typographic_covers.py            # dry run
    python scripts/backfill_typographic_covers.py --apply

Run it where the product's stores are reachable (inside the application container), with the same environment as
`scripts/audit_thumbnails.py`. Exit status: 0 done / nothing to do, 1 at least one item failed, 2 no usable store.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.thumbnail_audit import backfill, sources_from_environment  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    parser.add_argument("--apply", action="store_true", help="write the covers (default: dry run)")
    parser.add_argument("--all", action="store_true", help="media: also cover unpublished items")
    args = parser.parse_args(argv)
    try:
        sources = sources_from_environment(ROOT, args.url)
        report = backfill(sources, apply=args.apply, include_unpublished=args.all)
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never a URL
        print(f"refused: could not read the stores ({type(exc).__name__})")
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
