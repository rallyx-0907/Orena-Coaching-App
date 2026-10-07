"""Prepare the missing model clips of admitted media (D-140). Explicit, bounded, idempotent.

Run it inside the application image against the runtime you mean to change, for example the sandbox:

    docker exec orena-next-verify-web python scripts/backfill_model_clips.py --dry-run
    docker exec orena-next-verify-web python scripts/backfill_model_clips.py --max-lines 200

It reads the same media library and asset roots the application does (MEDIA_LIBRARY_ROOT,
MEDIA_LIBRARY_ASSET_ROOT) and never imports the application, so it starts no pipeline recovery.
A prepared line is skipped; --max-lines and --max-minutes bound one run, and a rerun continues.
No provider is called.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from writing_coach.book_asset_store import FilesystemBookAssetStore  # noqa: E402
from writing_coach.media_library_store import FileMediaLibraryStore  # noqa: E402
from writing_coach.model_clip_backfill import backfill  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="count what is missing; cut nothing")
    parser.add_argument("--media-id", action="append", dest="media_ids", help="limit to these lesson / media ids")
    parser.add_argument("--language", help="limit to one language code")
    parser.add_argument("--no-catalog", action="store_true", help="skip the curated catalogue")
    parser.add_argument("--no-imports", action="store_true", help="skip stored imports")
    parser.add_argument("--max-lines", type=int, default=200, help="most clips cut in one run")
    parser.add_argument("--max-minutes", type=float, default=30.0, help="most audio, in minutes, cut in one run")
    args = parser.parse_args(argv)
    library_root = Path(os.getenv("MEDIA_LIBRARY_ROOT", str(ROOT / "data" / "media_library")))
    asset_root = Path(os.getenv("MEDIA_LIBRARY_ASSET_ROOT", str(ROOT / "data" / "media_library_assets")))
    report = backfill(
        FileMediaLibraryStore(library_root),
        FilesystemBookAssetStore(asset_root),
        media_ids=args.media_ids,
        include_catalog=not args.no_catalog,
        include_entries=not args.no_imports,
        language=args.language,
        max_lines=max(0, args.max_lines),
        max_audio_ms=int(max(0.0, args.max_minutes) * 60_000),
        dry_run=args.dry_run,
    )
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
