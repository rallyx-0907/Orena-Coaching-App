"""Generate the development Listening catalog from the human source CSVs.

LISTENING_PRODUCT_SPEC 5. Reuses the existing YouTube provider adapter and the
canonical Media Learning Object; builds no second importer and downloads no
media.

    python scripts/build_listening_dev_catalog.py                  # both CSVs
    python scripts/build_listening_dev_catalog.py --limit 5        # a sample
    python scripts/build_listening_dev_catalog.py --report out.json

The generated manifest is only ever read when ENABLE_DEV_LISTENING_CATALOG is
set and APP_ENV is not production.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.listening_catalog import DEV_CATALOG_MANIFEST  # noqa: E402
from writing_coach.listening_dev_artifact import (  # noqa: E402
    SNAPSHOT_REQUIRED,
    verify_manifest_integrity,
)

DEFAULT_SOURCES = (
    ROOT / "writing_coach/content/listening_sources_en_dev_100.csv",
    ROOT / "writing_coach/content/listening_sources_zh_dev_100.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="*", type=Path, default=list(DEFAULT_SOURCES),
                        help="source CSV files (defaults to the EN and ZH development packs)")
    parser.add_argument("--out", type=Path, default=DEV_CATALOG_MANIFEST,
                        help="generated manifest path")
    parser.add_argument("--report", type=Path, default=None,
                        help="write the full per-candidate report as JSON")
    parser.add_argument("--limit", type=int, default=0,
                        help="import at most N candidates per file (0 = all)")
    parser.add_argument("--check", action="store_true",
                        help="verify the committed artifact's integrity and exit; no network")
    args = parser.parse_args()

    if args.check:
        # Offline: proves the committed snapshot matches its inputs and was not
        # hand-edited, without contacting a provider. Safe for CI.
        if not args.out.is_file():
            if SNAPSHOT_REQUIRED:
                print(f"FAIL: committed development catalog is missing at {args.out}",
                      file=sys.stderr)
                return 1
            # Never report integrity PASS for a file that does not exist.
            print(f"SKIP: no committed development catalog yet at {args.out}")
            print("      SNAPSHOT_REQUIRED is False; L3 commits the first snapshot "
                  "and flips it True.")
            return 0
        problem = verify_manifest_integrity(
            json.loads(args.out.read_text(encoding="utf-8")),
            content_dir=ROOT / "writing_coach/content",
        )
        if problem:
            print(f"FAIL: {problem}", file=sys.stderr)
            return 1
        print(f"generated catalog integrity OK: {args.out}")
        print("      content hash and every recorded source-list digest match.")
        return 0

    # Imported here, after --check, so verifying a committed artifact needs
    # neither the provider adapter nor its network dependencies.
    from writing_coach.listening_source_import import (
        ImportReport,
        build_dev_catalog,
        read_source_candidates,
        write_manifest,
    )
    from writing_coach.media_recovery_policy import build_youtube_adapter

    candidates = []
    for path in args.sources:
        if not path.is_file():
            print(f"source list not found: {path}", file=sys.stderr)
            return 2
        rows = read_source_candidates(path)
        candidates.extend(rows[: args.limit] if args.limit > 0 else rows)

    report = ImportReport()
    manifest, report = build_dev_catalog(candidates, build_youtube_adapter(), report)
    write_manifest(manifest, args.out, source_lists=list(args.sources))

    summary = report.as_dict()
    entries = summary.pop("entries")
    print(json.dumps(summary, indent=2))
    print(f"\nwrote {args.out}")
    if args.report:
        args.report.write_text(
            json.dumps({**summary, "entries": entries}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.report}")

    # A batch with no accepted candidate is a failure worth a non-zero exit;
    # individual failures are reported, never fatal.
    return 0 if summary["ACCEPTED"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
