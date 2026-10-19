"""Move published Reading and vocabulary between environments without an Admin browser session.

The same implementation as the Admin route `/api/admin/content-packs` (`writing_coach/content_pack_api.py`:
`run_export`, `plan_import`, `run_import`), run inside the target environment's application configuration, so the
Reading admission engine, the source and rights rules, the vocabulary normaliser and the publication rule decide
exactly as they do for an Admin import. Media travels with `scripts/media_content_pack.py` (or `--kinds media` here,
which uses the same code). Run it where the application's dependencies and its environment (database URLs) are:

    python scripts/content_pack.py export --kinds reading,vocabulary --dry-run [--language en]   # summary, writes nothing
    python scripts/content_pack.py export --kinds reading,vocabulary --out /tmp/x.orenapack \\
        [--language en|zh] [--source-slug-prefix sample-] [--exclude-source-prefix qa- --exclude-source-prefix test-]
    python scripts/content_pack.py import --pack /tmp/x.orenapack            # dry-run plan (the default)
    python scripts/content_pack.py import --pack /tmp/x.orenapack --apply    # writes, through the engines

`import` prints one row per item: `new`, `unchanged`, `conflict` (the target holds a different version; it is kept),
`held` (arrives only after an administrator there approves the source, or waits in the engine's own admission) or
`refused`, each with its reason. A re-run changes nothing. It writes content tables only (never learner data); an
imported Reading text is admitted by this environment's engine, which decides its status (nothing is auto-published
by the pack), and a new source arrives unapproved. `--overwrite` is passed to the shared import exactly as the route
passes it: it replaces differing media only; Reading and vocabulary already present are always kept. With `--apply` it
records an `admin.content_pack_import` audit row (actor `cli:<os user>` or `cli:<--actor>`) and appends one line to
`--log` (default `$CONTENT_PACK_LOG`, else beside the environment's `WRITING_DB` when that is outside this checkout,
else `~/.orena/content-pack-imports.jsonl`; never inside the repository). The work has committed before that line is
written, so a log that cannot be written is reported on stderr with the full record printed there instead; it never
undoes or hides the import. A pack is read within the same limits as the Admin route. Exit status: 0 clean, 1 an item
was refused or in conflict (or nothing to export), 2 the pack or the arguments were refused, 3 the work completed but
its log line could not be written.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from collections.abc import Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import HTTPException  # noqa: E402

from writing_coach import content_pack_api as api  # noqa: E402
from writing_coach import reading_admin_api as reading  # noqa: E402
from writing_coach.content_packs import (  # noqa: E402
    IDENTICAL,
    MAX_PACK_BYTES,
    NEW,
    SOURCE_NEEDED,
    PackError,
    read_pack,
)

LOG_NAME = "content-pack-imports.jsonl"
LOG_NOT_WRITTEN = 3


def default_log_path(environ: Mapping[str, str] | None = None) -> Path:
    """Where the evidence line goes when `--log` is not given: never inside the repository checkout."""

    env = os.environ if environ is None else environ
    if str(env.get("CONTENT_PACK_LOG") or "").strip():
        return Path(str(env["CONTENT_PACK_LOG"]).strip())
    writing_db = str(env.get("WRITING_DB") or "").strip()
    if writing_db:
        data_root = Path(writing_db).resolve().parent
        if not data_root.is_relative_to(ROOT.resolve()):
            return data_root / LOG_NAME
    return Path.home() / ".orena" / LOG_NAME


def _bootstrap() -> None:
    """Configure the engines from this environment, as the application does at start (no server is started)."""
    import app  # noqa: F401, PLC0415


def _admin(args: argparse.Namespace) -> dict[str, str]:
    actor = f"cli:{args.actor or getpass.getuser()}"
    return {"google_sub": actor, "email": actor}


def _http_detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        return f"{detail.get('code') or exc.status_code}: {detail.get('message') or detail}"
    return f"{exc.status_code}: {detail}"


def classify_plan(pack: Any, plan: dict[str, Any]) -> list[dict[str, Any]]:
    """The dry-run rows in the CLI's vocabulary. `refused` is decided here only for what an import is certain to fail."""

    pack_sources = {item.data["slug"] for item in pack.items if item.kind == "reading_source"}
    known = {source["slug"] for source in reading._content().list_sources()} if any(
        item.kind == "reading_article" for item in pack.items) else set()
    by_key = {(item.kind, item.natural_key): item for item in pack.items}
    rows = []
    for row in plan["items"]:
        status, reason = row["outcome"], ""
        if status == IDENTICAL:
            status = "unchanged"
        elif status == NEW:
            item = by_key.get((row["kind"], row["natural_key"]))
            if item is not None and item.kind == "reading_article" and item.data["source_slug"] not in known | pack_sources:
                status, reason = "refused", "pack_source_missing: the article's source is neither here nor in the pack"
            elif row.get("note") == SOURCE_NEEDED:
                status, reason = "held", "waits until an administrator here approves its source"
            elif item is not None and item.kind == "reading_source":
                reason = "arrives unapproved; an administrator here approves it once"
            elif item is not None and item.kind == "reading_article":
                reason = "goes to this environment's admission engine, which decides its status"
        elif status == "changed":
            status, reason = "conflict", "differs from this environment's version; the local one is kept"
        rows.append({"kind": row["kind"], "key": row["natural_key"], "status": status,
                     "reason": reason})
    return rows


def classify_results(report: dict[str, Any]) -> list[dict[str, Any]]:
    """The applied rows in the CLI's vocabulary, from the shared import's own results."""

    rows = []
    for row in report["items"]:
        result = str(row.get("result") or "")
        reason = ""
        if "outcome" in row and row.get("kind") == "media_item":
            status, reason = row["outcome"], str(row.get("reason") or "")
        elif result in {"failed"}:
            status, reason = "refused", str(row.get("category") or "failed")
        elif result == "waiting_for_source_approval":
            status, reason = "held", "the source is not approved here yet; approve it, then import again"
        elif result in {"imported", "source_created_for_review", "submitted"}:
            status = "new"
            if result == "source_created_for_review":
                reason = "source created unapproved; an administrator here approves it once"
            elif result == "submitted":
                reason = "submitted to this environment's admission engine, which decides its status"
            elif row.get("status") == "pending_review":
                reason = "vocabulary collection waits for review under this environment's publication rule"
        elif result in {"kept_local", "identical", "present"}:
            status = "unchanged"
            sets = [s for s in row.get("sets") or []]
            if any(str(s.get("result")) == "refused" for s in sets):
                status, reason = "refused", ", ".join(str(s.get("category")) for s in sets if s.get("result") == "refused")
            elif any(s.get("result") != "refused" for s in sets) or str(row.get("thumbnail") or "") in {"attached", "typographic"}:
                status, reason = "new", "comprehension set or thumbnail attached to the present article"
            elif str(row.get("thumbnail") or "").startswith("refused:"):
                status, reason = "refused", str(row["thumbnail"])
            elif row.get("outcome") == "changed":
                status, reason = "conflict", "differs from this environment's version; the local one is kept"
        else:
            status, reason = "refused", result or "unknown"
        rows.append({"kind": row.get("kind"), "key": row.get("natural_key"), "status": status, "reason": reason})
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        out[row["status"]] = out.get(row["status"], 0) + 1
    return out


def _append_log(path: Path, entry: dict[str, Any]) -> bool:
    """Append the evidence line. The work it records has already committed, so a failure here is reported (and the
    record printed on stderr, where it can be kept) - never raised over a finished import."""

    line = json.dumps({"at": datetime.now(UTC).isoformat(), **entry}, ensure_ascii=False)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        return True
    except OSError as exc:
        print(f"Log not written ({path}): {type(exc).__name__}: {exc.strerror or exc}. "
              f"The work is done and in the audit log; the line was:\n{line}", file=sys.stderr)
        return False


def export_command(args: argparse.Namespace) -> int:
    kinds = [kind.strip() for kind in args.kinds.split(",") if kind.strip()]
    body = api.ExportBody(kinds=kinds, languages=args.language, source_slug_prefix=args.source_slug_prefix,
                          exclude_source_slug_prefixes=args.exclude_source_prefix, collection_prefix=args.collection_prefix)
    try:
        raw, counts = api.run_export(_admin(args), body, dry_run=args.dry_run)
    except HTTPException as exc:
        print(f"Nothing exported: {_http_detail(exc)}", file=sys.stderr)
        return 1 if exc.status_code == 404 else 2
    report = {"dry_run": args.dry_run, "counts": counts, "bytes": len(raw), "pack": None}
    if not args.dry_run:
        out = Path(args.out)
        out.write_bytes(raw)
        report["pack"] = str(out)
        logged = _append_log(Path(args.log), {"command": "export", "actor": _admin(args)["google_sub"],
                                              "counts": counts, "pack": str(out), "bytes": len(raw)})
        report["log"] = str(args.log) if logged else None
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if args.dry_run or report["log"] else LOG_NOT_WRITTEN


def import_command(args: argparse.Namespace) -> int:
    try:
        # The route's limits (`read_pack`'s defaults): a pack the Admin import would refuse is refused here too.
        if Path(args.pack).stat().st_size > MAX_PACK_BYTES:
            raise PackError("pack_too_large", "This pack is larger than an import accepts.")
        pack = read_pack(Path(args.pack).read_bytes())
    except (PackError, OSError) as exc:
        print(f"Pack refused: {getattr(exc, 'code', 'pack_unreadable')}: {exc}", file=sys.stderr)
        return 2
    admin = _admin(args)
    try:
        if args.apply:
            rows = classify_results(api.run_import(admin, pack, overwrite=args.overwrite))
        else:
            rows = classify_plan(pack, reading._guarded(lambda: api.plan_import(pack, args.overwrite)))
    except HTTPException as exc:
        print(f"Import stopped: {_http_detail(exc)}", file=sys.stderr)
        return 2
    summary = _summary(rows)
    report = {"dry_run": not args.apply, "pack_id": pack.manifest.get("pack_id"), "summary": summary, "items": rows}
    logged = True
    if args.apply:
        logged = _append_log(Path(args.log), {"command": "import", "actor": admin["google_sub"],
                                              "pack_id": pack.manifest.get("pack_id"), "overwrite": args.overwrite,
                                              "summary": summary})
        report["log"] = str(args.log) if logged else None
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if summary.get("refused") or summary.get("conflict"):
        return 1
    return 0 if logged else LOG_NOT_WRITTEN


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("export", "import"):
        p = sub.add_parser(name)
        p.add_argument("--actor", default="", help="recorded as cli:<actor>; default the operating-system user")
        p.add_argument("--log", default=str(default_log_path()),
                       help="jsonl evidence file appended to (default: $CONTENT_PACK_LOG, else outside the repository)")
    ex, im = sub.choices["export"], sub.choices["import"]
    ex.add_argument("--kinds", default="reading,vocabulary", help="comma list of reading, vocabulary (media: see media_content_pack.py)")
    ex.add_argument("--language", action="append", default=[], choices=["en", "zh"])
    ex.add_argument("--source-slug-prefix", default="")
    ex.add_argument("--exclude-source-prefix", action="append", default=[], help="leave out Reading sources with this slug prefix")
    ex.add_argument("--collection-prefix", default="", help="only vocabulary collections whose id starts with this")
    ex.add_argument("--out", default="")
    ex.add_argument("--dry-run", action="store_true", help="print what would be packed; write nothing")
    im.add_argument("--pack", required=True)
    im.add_argument("--apply", action="store_true", help="write; without it the import is a dry-run plan")
    im.add_argument("--overwrite", action="store_true", help="as the route: replaces differing media only")
    return parser


def main(argv: list[str] | None = None, *, bootstrap: Any = _bootstrap) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "export" and not args.dry_run and not args.out:
        parser.error("export needs --out (or --dry-run)")
    bootstrap()
    return export_command(args) if args.command == "export" else import_command(args)


if __name__ == "__main__":
    raise SystemExit(main())
