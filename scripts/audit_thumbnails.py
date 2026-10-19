"""Read-only audit: published items that have no thumbnail, per kind (D-240).

Every learner-visible Reading article, vocabulary collection, book and media item must have a thumbnail. Publishing
without one is refused; this lists what was published before that rule so it can be given one
(`scripts/backfill_typographic_covers.py`). It writes nothing and unpublishes nothing; the database URL is never printed.

    python scripts/audit_thumbnails.py            # published items only, JSON on stdout
    python scripts/audit_thumbnails.py --all      # media: also unpublished items (each row says `published`)

Run it where the product's stores are reachable (inside the application container): `POSTGRES_RUNTIME_URL`,
`READING_LIBRARY_ASSET_ROOT`, `MEDIA_LIBRARY_ROOT`, `MEDIA_LIBRARY_ASSET_ROOT`.

Exit status: 0 nothing is missing, 1 at least one published item has no thumbnail, 2 no usable store.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.thumbnail_audit import audit, sources_from_environment  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--url", default="", help="defaults to POSTGRES_RUNTIME_URL; never printed")
    parser.add_argument("--all", action="store_true", help="media: also list unpublished items")
    args = parser.parse_args(argv)
    try:
        sources = sources_from_environment(ROOT, args.url)
        report = audit(sources, include_unpublished=args.all)
    except Exception as exc:  # noqa: BLE001 - report the kind of failure, never a URL
        print(f"refused: could not read the stores ({type(exc).__name__})")
        return 2
    if not report["missing"]:
        print("refused: no store could be opened")
        return 2
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 1 if report["total_missing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
