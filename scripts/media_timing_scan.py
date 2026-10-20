"""Periodic caption-timing scan of the shared media library (P0 2026-10-20). Dry run by default.

    python scripts/media_timing_scan.py                       # dry run: report only, writes nothing but the JSON report
    python scripts/media_timing_scan.py --apply               # holds every failing published item for timing review
    python scripts/media_timing_scan.py --status any --id youtube-ZncA70OAgPw

Every shared entry whose transcript came from provider captions (published ones by default) is run through the one
caption-timing gate (`media_transcript_pipeline.caption_timing_gate`, the same function ingest, content-pack import and
Publish use). The report is JSON: one row per item checked, with the gate's counts and, for a failing item, what to do.

`--apply` changes only items that fail: status `review`, `processing.state = held`, reason `caption_timing` (the timing
review state the pipeline itself uses), the stored transcript left exactly as it is. It does not re-time anything itself:
the provider's raw cues are not stored with an item, only the lines already cut from them, so a mistimed item is re-timed
by the existing Reprocess action, which fetches the captions again and cuts them with the fixed rule (no audio is
downloaded, D-244). Each failing row says `"retime": "reprocess"`. Run `--apply` only with the owner's approval and while
no import is running; the index write is the store's own atomic replace.

The report goes to `--out`, else `$ORENA_HEALTH_DIR/media_timing_scan.json`, else `~/.orena/health/media_timing_scan.json`
(the folder `scripts/health_check_8000.ps1` keeps its `health.log` in). `--health-line` also prints one line in that log's
format (`PASS media-timing ...` / `FAIL media-timing ...`) for the health check to append.

Exit code: 0 when every checked item passes (or `--apply` held every one that failed), 1 when a dry run found failures,
2 when the index cannot be read.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.media_caption_timing import (  # noqa: E402
    REASON_CAPTION_TIMING,
    TimingThresholds,
    caption_timing_report,
    classify_caption_kind,
    lesson_caption_facts,
    thresholds,
)
from writing_coach.media_library_store import MEDIA_LIBRARY_ROOT, FileMediaLibraryStore  # noqa: E402


def _default_out() -> Path:
    base = os.getenv("ORENA_HEALTH_DIR") or str(Path.home() / ".orena" / "health")
    return Path(base) / "media_timing_scan.json"


def _lines(entry: Any) -> list[Any]:
    from writing_coach.media_transcript_pipeline import lines_from_payload

    return lines_from_payload((entry.lesson or {}).get("payload") if entry.lesson else None)


def scan(store: FileMediaLibraryStore, *, status: str | None, ids: list[str], limits: TimingThresholds) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entry in store.list(status=status):
        if ids and entry.media_id not in ids:
            continue
        applies, kind, retimed = lesson_caption_facts(entry)
        if not applies:
            continue
        lines = _lines(entry)
        classified = classify_caption_kind(kind, lines)
        report = caption_timing_report(lines, language=entry.language, caption_kind=classified, retimed=retimed, limits=limits)
        fast_share = round(report.counts.get("fast", 0) / report.lines, 3) if report.lines else 0.0
        rows.append({
            "media_id": entry.media_id, "title": entry.title[:120], "language": entry.language, "status": entry.status,
            "caption_provider": str((entry.source or {}).get("caption_provider") or ""),
            "caption_kind": kind or "", "classified_kind": classified, "retimed": retimed,
            "fast_share": fast_share, **report.as_dict(),
            **({} if report.passed else {"retime": "reprocess", "detail": report.detail()[:200]}),
        })
    return rows


def hold(store: FileMediaLibraryStore, media_id: str, detail: str) -> bool:
    from writing_coach.media_transcript_pipeline import reason_message

    def change(fresh: Any) -> Any:
        processing = dict(fresh.processing or {})
        processing.update(state="held", reason=REASON_CAPTION_TIMING, detail=detail, auto_published=False,
                          message=reason_message(REASON_CAPTION_TIMING),
                          updated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        lesson = dict(fresh.lesson or {})
        if lesson:
            lesson["status"] = "NEEDS_REVIEW"
        return replace(fresh, status="review", processing=processing, lesson=lesson or fresh.lesson)

    return store.update_if_present(media_id, change) is not None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", type=Path, default=MEDIA_LIBRARY_ROOT, help="media library root (holds index.json)")
    parser.add_argument("--status", default="published", help="published (default), review, unpublished, or any")
    parser.add_argument("--id", action="append", default=[], help="only this media id (repeatable)")
    parser.add_argument("--apply", action="store_true", help="hold every failing item for timing review")
    parser.add_argument("--out", type=Path, default=None, help="JSON report path")
    parser.add_argument("--health-line", action="store_true", help="print one health.log line")
    parser.add_argument("--max-cps", type=float, default=None)
    parser.add_argument("--max-cps-zh", type=float, default=None)
    parser.add_argument("--max-defect-share", type=float, default=None)
    args = parser.parse_args(argv)

    base = thresholds()
    limits = TimingThresholds(
        max_cps=args.max_cps if args.max_cps is not None else base.max_cps,
        max_cps_zh=args.max_cps_zh if args.max_cps_zh is not None else base.max_cps_zh,
        max_defect_share=args.max_defect_share if args.max_defect_share is not None else base.max_defect_share,
        max_gap_ms=base.max_gap_ms,
    )
    store = FileMediaLibraryStore(args.root)
    rows = scan(store, status=None if args.status == "any" else args.status, ids=args.id, limits=limits)
    if store.last_read_issue in {"index_corrupt", "index_unreadable"}:
        print(f"media index unreadable: {store.last_read_issue}", file=sys.stderr)
        return 2
    failing = [row for row in rows if not row["pass"]]
    held: list[str] = []
    if args.apply:
        for row in failing:
            if hold(store, row["media_id"], row.get("detail", "")):
                held.append(row["media_id"])
    report = {
        "scanned_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "mode": "apply" if args.apply else "dry_run",
        "thresholds": {"max_cps": limits.max_cps, "max_cps_zh": limits.max_cps_zh,
                       "max_defect_share": limits.max_defect_share, "max_gap_ms": limits.max_gap_ms},
        "checked": len(rows), "failing": len(failing), "held": held, "retimed": 0,
        "items": rows,
    }
    out = args.out or _default_out()
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"report not written to {out}: {error}", file=sys.stderr)
    print(json.dumps({key: report[key] for key in ("mode", "checked", "failing", "held")}, ensure_ascii=False))
    if args.health_line:
        word = "PASS" if not failing or (args.apply and len(held) == len(failing)) else "FAIL"
        print(f"{word} media-timing checked={len(rows)} failing={len(failing)} held={len(held)}")
    if not failing:
        return 0
    return 0 if args.apply and len(held) == len(failing) else 1


if __name__ == "__main__":
    raise SystemExit(main())
