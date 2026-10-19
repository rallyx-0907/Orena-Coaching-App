"""Move published shared-library media between environments (D-234). No provider is called, no job is started.

Run it where the application's Python dependencies are (the application image or its virtualenv), against the media
library roots of the environment (`MEDIA_LIBRARY_ROOT`, `MEDIA_LIBRARY_ASSET_ROOT`, or `--root` / `--asset-root`):

    python scripts/media_content_pack.py export --dry-run [--language en] [--id ID ...]      # summary, writes nothing
    python scripts/media_content_pack.py export --out /tmp/media.orenapack [--language en] [--id ID ...] \
        [--exclude-prefix qa- --exclude-prefix test-] [--environment lane-8021]
    python scripts/media_content_pack.py import --pack /tmp/media.orenapack                  # dry run (the default)
    python scripts/media_content_pack.py import --pack /tmp/media.orenapack --apply          # writes
    python scripts/media_content_pack.py import --pack /tmp/media.orenapack --apply --overwrite

`export` reads only shared entries with status `published`, and each one's stored cue translations from the learning
cache Listening reads (`LEARNING_CACHE_DB`, else `<root>/learning_cache.db`, or `--learning-cache`) under the translating
identities found in the AI ledger (`--ledger-csv`, or PostgreSQL when POSTGRES_RUNTIME_URL is set; `--provider-model` overrides) and keeps the newest per cue; coverage below 100% warns and exits 3 unless `--allow-partial`. `import` is a dry run
unless `--apply` is given, prints one row per item (new / unchanged / conflict / refused, with the reason, and the
translations it would write), and exits 0 when no item was refused or in conflict. With `--apply` it puts the
translations into the target's learning cache as `pack-import` rows, so Listening serves them with no
provider call, and appends one line to `media-pack-imports.jsonl` beside the index. Back up the target's media library
root and learning cache before the first `--apply`. The same implementation is the Admin route
(`/api/admin/content-packs`, kind `media`); this script is for packs too large for an upload.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach import media_pack  # noqa: E402
from writing_coach.book_asset_store import FilesystemBookAssetStore  # noqa: E402
from writing_coach.content_packs import PackError, build_pack, read_pack  # noqa: E402
from writing_coach.media_library_store import FileMediaLibraryStore  # noqa: E402
from writing_coach.persistence.learning_repository import (  # noqa: E402
    SQLiteLearningCacheRepository,
    SQLiteLearningRepository,
)

GIB = 1024**3
AUDIT_FILE = "media-pack-imports.jsonl"


def _roots(args: argparse.Namespace) -> tuple[Path, Path]:
    root = Path(args.root or os.getenv("MEDIA_LIBRARY_ROOT") or ROOT / "data" / "media_library")
    assets = Path(args.asset_root or os.getenv("MEDIA_LIBRARY_ASSET_ROOT") or ROOT / "data" / "media_library_assets")
    return root, assets


def _cache_path(args: argparse.Namespace, root: Path) -> Path:
    """The file `app._learning_cache_path` resolves to."""
    return Path(args.learning_cache or os.getenv("LEARNING_CACHE_DB") or root / "learning_cache.db")


def _open_cache(path: Path, *, init: bool = False) -> SQLiteLearningCacheRepository:
    cache = SQLiteLearningCacheRepository(lambda: SQLiteLearningRepository(lambda: path).connect())
    if init:
        cache.initialize()
    return cache


def _provider_models(args: argparse.Namespace) -> list[str]:
    """Every identity a stored meaning's cache key may carry: `--provider-model` overrides first, then the AI ledger's
    distinct media_translation provider/model pairs (`--ledger-csv` rows, or the PostgreSQL ledger when
    POSTGRES_RUNTIME_URL is set), then this environment's configured model."""
    models = [m for m in (args.provider_model or []) if m]
    rows = []
    if args.ledger_csv:
        with Path(args.ledger_csv).open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    models += media_pack.models_from_ledger_rows(rows)
    if os.getenv("POSTGRES_RUNTIME_URL") and not args.no_ledger:
        from writing_coach.persistence.platform_repository import PostgresPlatformRepository

        models = media_pack.discover_provider_models(PostgresPlatformRepository(url=os.environ["POSTGRES_RUNTIME_URL"]), models)
    models.append(f"GroqTranslationProvider:{os.getenv('GROQ_TRANSLATION_MODEL', 'openai/gpt-oss-120b')}")
    return list(dict.fromkeys(models))


def _commit() -> str:
    if os.getenv("ORENA_COMMIT"):
        return os.environ["ORENA_COMMIT"][:40]
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        return out.stdout.strip()[:40] if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def export_command(args: argparse.Namespace) -> int:
    root, asset_root = _roots(args)
    store, assets = FileMediaLibraryStore(root), FilesystemBookAssetStore(asset_root)
    cache_file = _cache_path(args, root)
    # Read-only: a cache file that is absent is not created by an export; no translation is then exported.
    cache = _open_cache(cache_file) if cache_file.is_file() else None
    items, blobs, excluded = media_pack.build_media_items(
        store, assets, ids=args.id, languages=args.language, exclude_prefixes=args.exclude_prefix,
        translations=cache, provider_models=_provider_models(args))
    coverage = media_pack.translation_coverage(items)
    partial = bool(items) and not coverage["complete"]
    if partial:
        total = coverage["total"]
        print(f"WARNING: stored translations cover {total['percent']}% of the cues ({total['have']}/{total['expected']}); "
              f"incomplete items: {', '.join(coverage['incomplete'][:30])}. Probed: {', '.join(_provider_models(args))}. "
              "Pass --provider-model / --ledger-csv for a model not probed, or --allow-partial to export anyway.",
              file=sys.stderr)
    if args.dry_run:
        print(json.dumps(media_pack.export_preview(items, blobs, excluded), ensure_ascii=False, indent=2))
        return 0 if items and not (partial and not args.allow_partial) else (3 if partial else 1)
    if partial and not args.allow_partial:
        print("No pack written (coverage below 100%).", file=sys.stderr)
        return 3
    if not items:
        print(json.dumps({"exported": 0, "excluded": excluded}, indent=2))
        print("Nothing published matches; no pack written.", file=sys.stderr)
        return 1
    version_file = ROOT / "VERSION"
    raw = build_pack(
        items, created_by="cli", environment=args.environment, assets=blobs,
        app_version=version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else "",
        filters={"kinds": ["media"], "languages": args.language, "media_ids": args.id,
                 "exclude_media_id_prefixes": args.exclude_prefix},
        extra_manifest={"source_commit": _commit(), "media_excluded": excluded},
    )
    out = Path(args.out)
    out.write_bytes(raw)
    translations = sum(sum(media_pack.translation_counts(item).values()) for item in items)
    print(json.dumps({"exported": len(items), "assets": len(blobs), "translations": translations, "coverage": coverage["total"], "bytes": len(raw),
                      "excluded": excluded, "pack": str(out)}, indent=2))
    return 0


def import_command(args: argparse.Namespace) -> int:
    root, asset_root = _roots(args)
    try:
        pack = read_pack(Path(args.pack).read_bytes(), max_pack_bytes=2 * GIB, max_total_bytes=4 * GIB,
                         max_file_bytes=1 * GIB)
    except PackError as exc:
        print(f"Pack refused: {exc.code}: {exc}", file=sys.stderr)
        return 2
    store, assets = FileMediaLibraryStore(root), FilesystemBookAssetStore(asset_root)
    cache_file = _cache_path(args, root)
    # A dry run never creates the cache file; it reads one that is there, and counts everything as new otherwise.
    cache = _open_cache(cache_file, init=args.apply) if args.apply or cache_file.is_file() else _EmptyCache()
    rows = media_pack.apply_media_items(pack, store, assets, overwrite=args.overwrite, dry_run=not args.apply,
                                        actor="cli", translations=cache)
    summary = media_pack.summarize(rows)
    print(json.dumps({"dry_run": not args.apply, "pack_id": pack.manifest.get("pack_id"),
                      "pack_version": pack.manifest.get("version"), "summary": summary,
                      "translations": media_pack.translation_totals(rows), "items": rows},
                     ensure_ascii=False, indent=2))
    if args.apply:
        root.mkdir(parents=True, exist_ok=True)
        with (root / AUDIT_FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": datetime.now(UTC).isoformat(), "pack_id": pack.manifest.get("pack_id"),
                                     "overwrite": args.overwrite, "summary": summary,
                                     "translations": media_pack.translation_totals(rows)}, ensure_ascii=False) + "\n")
    return 1 if summary.get(media_pack.REFUSED) or summary.get(media_pack.CONFLICT) else 0


class _EmptyCache:
    """Stands in for a cache file that does not exist yet, so a dry run reads it as empty and creates nothing."""

    def get_media_translation(self, key: str) -> None:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "import"):
        p = sub.add_parser(name)
        p.add_argument("--root", default="", help="media library root (index.json); default MEDIA_LIBRARY_ROOT")
        p.add_argument("--asset-root", default="", help="asset root; default MEDIA_LIBRARY_ASSET_ROOT")
        p.add_argument("--learning-cache", default="", help="learning cache db holding stored cue translations; "
                       "default LEARNING_CACHE_DB, else <root>/learning_cache.db")
        p.add_argument("--provider-model", action="append", default=[],
                       help="override: a translating identity the cache keys carry, e.g. "
                       "GroqTranslationProvider:<model>; added to the ledger's models")
        p.add_argument("--ledger-csv", default="", help="AI ledger rows (capability,provider,model,...) to read the "
                       "translating models from, e.g. a cost export")
        p.add_argument("--no-ledger", action="store_true", help="do not read the PostgreSQL ledger")
    ex, im = sub.choices["export"], sub.choices["import"]
    ex.add_argument("--out", default="")
    ex.add_argument("--allow-partial", action="store_true",
                    help="export although stored translations cover less than 100% of the cues (exit 3 otherwise)")
    ex.add_argument("--dry-run", action="store_true", help="print what would be packed (with translation counts); write nothing")
    ex.add_argument("--id", action="append", default=[])
    ex.add_argument("--language", action="append", default=[], choices=["en", "zh"])
    ex.add_argument("--exclude-prefix", action="append", default=[])
    ex.add_argument("--environment", default=os.getenv("ORENA_ENVIRONMENT_LABEL", "local"))
    im.add_argument("--pack", required=True)
    im.add_argument("--apply", action="store_true", help="write; without it the import is a dry run")
    im.add_argument("--overwrite", action="store_true", help="replace an existing item or translation that differs")
    args = parser.parse_args(argv)
    if args.command == "export" and not args.dry_run and not args.out:
        parser.error("export needs --out (or --dry-run)")
    return export_command(args) if args.command == "export" else import_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
