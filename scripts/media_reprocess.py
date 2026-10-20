"""Re-run the Admin "Reprocess" of shared media items, captions only, one at a time (PR BU). Dry run by default.

    python scripts/media_reprocess.py --id youtube-ZncA70OAgPw --actor hermes-for-owner            # dry run
    python scripts/media_reprocess.py --from-scan ~/.orena/health/media_timing_scan.json --actor X  # dry run
    python scripts/media_reprocess.py --from-scan <report.json> --actor X --apply                    # re-run them

What `--apply` runs is the Admin route's own Reprocess (`POST /api/admin/console/content/media/{id}/reprocess`, scope `all`):
`media_library_api.retry_transcript`, i.e. `MediaPipeline.retry`. That re-run fetches the provider's captions again and
cuts them with the current timing rule (#430); it never downloads audio (D-244), and this CLI also takes the recogniser
and the audio downloader out of its own process to make that certain. Only an item whose stored transcript is the
provider's captions, in a good state (ready or held, with a usable transcript), is re-run, so `_keeps_captions` holds: if
the captions cannot be had this time, the item keeps the transcript it has. The Supadata daily cap
(`media.supadata_daily_requests`) is enforced by the caption source before every call; this CLI also stops before an
item when today's count has already reached the cap. A re-run that fails puts the item back exactly as it was (#430's
snapshot and restore), and says why in `reprocess_reason`.

Owner rule (import at human pace): items run ONE at a time, inline, and the run stops at the first anomaly: an item that
is not eligible, a re-run that was restored, still running, held for timing, or whose caption timing report (#430's
`caption_timing_report`, the same as `media_timing_scan.py`) fails afterwards. Items after the anomaly are not touched;
fix or decide, then run again with what is left.

Each re-run is recorded in `audit_logs` as `admin.content.reprocess` (the event the route records) with the `--actor`,
`via: scripts/media_reprocess.py` and the outcome. Nothing is deleted.

The full sequence after a timing scan found failures:
    1. python scripts/media_timing_scan.py                                    # dry run: the JSON report of failing items
    2. python scripts/media_reprocess.py --from-scan <that report> --actor X  # dry run: who is eligible, the cap
    3. python scripts/media_reprocess.py --from-scan <that report> --actor X --apply
    4. python scripts/media_timing_scan.py --apply                            # anything still failing is held for review
Run step 3 only while no import is running (the Admin's processing list shows none queued or running).

Output: one JSON report (`checked`, `eligible`, `reprocessed`, `passed`, `stopped_at`, one row per item).
Exit code: 0 every item done (or, dry run, every item eligible); 1 stopped at an anomaly (or, dry run, an item is not
eligible); 2 the run could not start (no actor, no index, no audit log for `--apply`).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.operator_cli import OperatorRefused, emit, refused, require_actor  # noqa: E402

SCRIPT = "scripts/media_reprocess.py"
GOOD_STATES = {"ready", "held"}
BUSY_STATES = {"queued", "running"}


def ids_from_scan(path: Path) -> list[str]:
    """The failing items of a `media_timing_scan.py` report, in its order."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise OperatorRefused("scan_unreadable", f"{path.name}: {type(error).__name__}") from error
    items = report.get("items") if isinstance(report, Mapping) else None
    if not isinstance(items, list):
        raise OperatorRefused("scan_unreadable", f"{path.name}: no items")
    return [str(row["media_id"]) for row in items if isinstance(row, Mapping) and row.get("media_id") and not row.get("pass", True)]


def ineligible(entry: Any) -> str:
    """Why this item may not be re-run here, or '' when it may (captions only, restorable)."""
    from writing_coach.media_transcript_pipeline import ORIGIN_CAPTION, usable_transcript

    if entry is None:
        return "not_found"
    if entry.library != "shared":
        return "not_shared"
    if entry.provider != "youtube" or not entry.canonical_url:
        return "not_youtube_captions"
    processing = entry.processing or {}
    state = str(processing.get("state") or "")
    if state in BUSY_STATES:
        return "busy"
    if state not in GOOD_STATES:
        # Without a good state there is no snapshot to put back if the re-run fails.
        return f"state_{state or 'unknown'}"
    payload = (entry.lesson or {}).get("payload") if isinstance(entry.lesson, Mapping) else None
    if not isinstance(payload, Mapping) or payload.get("transcript_origin") != ORIGIN_CAPTION:
        return "not_provider_captions"
    ok, reason = usable_transcript(entry)
    if not ok:
        return f"transcript_{reason}"
    return ""


def timing(store: Any, media_id: str, limits: Any) -> dict[str, Any] | None:
    from scripts.media_timing_scan import scan

    rows = scan(store, status=None, ids=[media_id], limits=limits)
    return rows[0] if rows else None


def _state(entry: Any) -> dict[str, str]:
    processing = (entry.processing or {}) if entry is not None else {}
    return {"status": getattr(entry, "status", "") or "", "state": str(processing.get("state") or ""),
            "reason": str(processing.get("reason") or "")}


def _timing_summary(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row.get(key) for key in ("pass", "lines", "counts", "detail") if key in row}


def run(
    ids: list[str],
    *,
    store: Any,
    apply: bool,
    actor: str,
    limits: Any,
    retry: Callable[[str], bool] | None = None,
    record_event: Callable[..., None] | None = None,
    quota: Callable[[], tuple[int, int]] | None = None,
) -> tuple[dict[str, Any], int]:
    from writing_coach.media_caption_timing import REASON_CAPTION_TIMING

    if apply and (retry is None or record_event is None):
        raise OperatorRefused("apply_unavailable", "the pipeline or the audit log is not available")
    rows: list[dict[str, Any]] = []
    stopped: dict[str, str] | None = None
    reprocessed = passed = 0
    for media_id in ids:
        entry = store.get(media_id)
        why = ineligible(entry)
        before = _state(entry)
        row: dict[str, Any] = {"media_id": media_id, "title": (getattr(entry, "title", "") or "")[:120], "before": before}
        if why:
            row["outcome"] = f"ineligible:{why}"
            rows.append(row)
            stopped = stopped or {"media_id": media_id, "anomaly": row["outcome"]}
            if apply:
                break
            continue
        if not apply:
            row["outcome"] = "would_reprocess"
            row["timing_now"] = _timing_summary(timing(store, media_id, limits))
            rows.append(row)
            continue
        if quota is not None:
            used, cap = quota()
            if used >= cap:
                row["outcome"] = "caption_quota"
                row["quota"] = {"used_today": used, "cap": cap}
                rows.append(row)
                stopped = {"media_id": media_id, "anomaly": "caption_quota"}
                break
        started = bool(retry(media_id))  # type: ignore[misc]
        after_entry = store.get(media_id)
        after = _state(after_entry)
        processing = (after_entry.processing or {}) if after_entry is not None else {}
        report = timing(store, media_id, limits) if after_entry is not None else None
        anomaly = ""
        if not started:
            anomaly = "not_retried"
        elif after_entry is None:
            anomaly = "vanished"
        elif after["state"] in BUSY_STATES:
            anomaly = "still_running"
        elif processing.get("reprocess_reason"):
            anomaly = f"restored:{processing.get('reprocess_reason')}"   # the re-run failed; the item is back as it was
        elif after["state"] not in GOOD_STATES:
            anomaly = f"state_{after['state'] or 'unknown'}"
        elif after["reason"] == REASON_CAPTION_TIMING:
            anomaly = "held_caption_timing"
        elif before["state"] == "ready" and after["state"] == "held":
            anomaly = f"held:{after['reason'] or 'unknown'}"
        elif report is None:
            anomaly = "timing_not_applicable"
        elif not report.get("pass"):
            anomaly = "timing_fail"
        if started:
            reprocessed += 1
        ok = not anomaly
        passed += int(ok)
        row.update(after=after, timing_pass=bool(report and report.get("pass")), timing=_timing_summary(report),
                   outcome="ok" if ok else anomaly)
        print(f"{media_id}: timing {'PASS' if row['timing_pass'] else 'FAIL'} ({row['outcome']})", file=sys.stderr)
        if started:
            record_event("admin.content.reprocess", actor_key=actor, entity_type="media", entity_id=media_id,  # type: ignore[misc]
                         payload={"outcome": "ok" if ok else "failed", "scope": "captions", "via": SCRIPT, "actor": actor,
                                  "anomaly": anomaly, "timing_pass": row["timing_pass"]})
        rows.append(row)
        if not ok:
            stopped = {"media_id": media_id, "anomaly": anomaly}
            break
    eligible = sum(1 for row in rows if not row["outcome"].startswith("ineligible:") and row["outcome"] != "caption_quota")
    report_out = {
        "script": SCRIPT, "mode": "apply" if apply else "dry_run", "actor": actor,
        "requested": len(ids), "checked": len(rows), "eligible": eligible,
        "reprocessed": reprocessed, "passed": passed, "not_reached": len(ids) - len(rows),
        "stopped_at": stopped, "items": rows,
    }
    if quota is not None:
        used, cap = quota()
        report_out["caption_quota"] = {"used_today": used, "cap": cap}
    return report_out, (1 if stopped else 0)


def _quota_reader(ledger: Any) -> Callable[[], tuple[int, int]]:
    from writing_coach import policies

    return lambda: (int(ledger.requests_today()), int(policies.value("media.supadata_daily_requests")))


def _wire_apply() -> tuple[Any, Callable[[str], bool], Callable[..., None], Callable[[], tuple[int, int]]]:
    """The running app's own wiring: the store, the pipeline and the audit log the Admin route uses."""
    # One item at a time, on this thread: the re-run finishes before the next item is looked at.
    os.environ["MEDIA_PIPELINE_INLINE"] = "1"
    import app as app_module  # noqa: F401 - configures the media library exactly as the server does
    from writing_coach import media_library_api
    from scripts.operator_cli import audit_recorder

    store, _assets, importer = media_library_api._installed()
    pipeline = importer.pipeline
    if pipeline is None:
        raise OperatorRefused("pipeline_unavailable")
    # Captions only (D-244): this process can neither download audio nor recognise speech, whatever the item says.
    pipeline._asr = None
    pipeline._youtube_audio = None
    engine = getattr(app_module._persistence_runtime, "engine", None)
    if engine is None:
        raise OperatorRefused("audit_unavailable", "no database engine: the re-run could not be recorded")
    return store, media_library_api.retry_transcript, audit_recorder(engine), _quota_reader(pipeline.ledger)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--id", action="append", default=[], help="a shared media id (repeatable, run in this order)")
    parser.add_argument("--from-scan", type=Path, default=None, help="a media_timing_scan.py JSON report: its failing ids")
    parser.add_argument("--apply", action="store_true", help="re-run them (default: dry run)")
    parser.add_argument("--actor", default="", help="who is acting; recorded with every re-run")
    parser.add_argument("--root", type=Path, default=None, help="dry run only: media library root (holds index.json)")
    args = parser.parse_args(argv)
    try:
        actor = require_actor(args.actor)
        ids = list(dict.fromkeys([*args.id, *(ids_from_scan(args.from_scan) if args.from_scan else [])]))
        if not ids:
            raise OperatorRefused("no_items", "pass --id or --from-scan")
        from writing_coach.media_caption_timing import thresholds

        if args.apply:
            store, retry, record_event, quota = _wire_apply()
        else:
            from writing_coach.media_library_store import MEDIA_LIBRARY_ROOT, FileMediaLibraryStore
            from writing_coach.media_spend import SpendLedger

            root = args.root or MEDIA_LIBRARY_ROOT
            store, retry, record_event = FileMediaLibraryStore(root), None, None
            quota = _quota_reader(SpendLedger(root / "processing-spend.json"))
        if getattr(store, "list", None) is not None:
            store.list(status=None)
            if getattr(store, "last_read_issue", "") in {"index_corrupt", "index_unreadable"}:
                raise OperatorRefused("index_unreadable", store.last_read_issue)
        report, code = run(ids, store=store, apply=args.apply, actor=actor, limits=thresholds(), retry=retry,
                           record_event=record_event, quota=quota)
    except OperatorRefused as error:
        return refused(SCRIPT, error)
    emit(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
