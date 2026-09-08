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


# The outcome that means "we could not find out", as opposed to any outcome
# that means "we found out". Only these are worth another pass.
UNRESOLVED_DETAIL = "unresolved, retry before judging"


def _merge(base: dict, extra: dict) -> dict:
    """Combine two generated manifests, keeping one entry per stable id."""

    sources = {item["source_media_id"]: item for item in base.get("sources", [])}
    lessons = {item["lesson_id"]: item for item in base.get("lessons", [])}
    for item in extra.get("sources", []):
        sources[item["source_media_id"]] = item
    for item in extra.get("lessons", []):
        lessons[item["lesson_id"]] = item
    return {
        "schema_version": 1,
        "sources": sorted(sources.values(), key=lambda item: item["source_media_id"]),
        "lessons": sorted(lessons.values(), key=lambda item: item["lesson_id"]),
    }


def _run_with_retries(
    candidates,
    *,
    pause_seconds,
    retry_passes,
    retry_backoff,
    adapter_factory=None,
    sleep=None,
):
    """Import every candidate, retrying only those left genuinely unresolved.

    `adapter_factory` and `sleep` exist so this can be tested without a network
    or a real wait; production always uses the shared recovery policy's adapter.
    """

    import time
    from writing_coach.listening_source_import import ImportReport, build_dev_catalog
    from writing_coach.media_recovery_policy import build_youtube_adapter

    adapter_factory = adapter_factory or build_youtube_adapter
    rest = sleep or time.sleep

    remaining = list(candidates)
    manifest: dict = {"schema_version": 1, "sources": [], "lessons": []}
    # candidate_id -> its latest outcome entry, so a retry replaces the earlier
    # unresolved record instead of adding a second one for the same candidate.
    final: dict[str, dict] = {}

    for attempt in range(retry_passes + 1):
        if attempt:
            print(
                f"retry pass {attempt}: {len(remaining)} unresolved candidate(s); "
                  f"resting {retry_backoff:.0f}s", flush=True)
            rest(retry_backoff)
        rows = _paced(remaining, pause_seconds) if pause_seconds > 0 else remaining
        chunk, chunk_report = build_dev_catalog(rows, adapter_factory(), ImportReport())
        manifest = _merge(manifest, chunk)
        summary = chunk_report.as_dict()
        for entry in summary["entries"]:
            final[entry["candidate_id"]] = entry

        unresolved = {entry["candidate_id"] for entry in summary["entries"]
                      if UNRESOLVED_DETAIL in entry["detail"]}
        remaining = [row for row in remaining if row.candidate_id in unresolved]
        if not remaining or attempt == retry_passes:
            break

    # Rebuild one report from the final per-candidate outcomes, so the counts
    # describe the end state rather than the sum of every attempt.
    report = ImportReport()
    for entry in final.values():
        report.record(entry["candidate_id"], entry["outcome"], entry["detail"],
                      entry.get("language", ""))
    report.generated_sources = len(manifest["sources"])
    by_source = {item["source_media_id"]: item for item in manifest["sources"]}
    per_source: dict[str, int] = {}
    for lesson in manifest["lessons"]:
        source = by_source.get(lesson["source_media_id"])
        language = source["language"] if source else ""
        report.record_lesson(language, lesson["estimated_level"], lesson["topic"])
        per_source[lesson["source_media_id"]] = per_source.get(lesson["source_media_id"], 0) + 1
    for count in per_source.values():
        report.excerpts_per_source[count] += 1
    return manifest, report


def _paced(candidates, seconds: float):
    """Yield candidates with a gap, so the provider does not rate-limit us."""

    import time
    for index, candidate in enumerate(candidates):
        if index:
            time.sleep(seconds)
        yield candidate


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
    parser.add_argument("--offline-transcripts", type=Path, default=None,
                        help="JSON of already-acquired canonical transcripts, keyed "
                             "by video id. Lets a machine with provider access "
                             "acquire once and this machine build with no network. "
                             "Same pipeline, same provenance rules.")
    parser.add_argument("--retry-passes", type=int, default=0,
                        help="extra passes over candidates left UNRESOLVED by a "
                             "failed caption request. Provider throttling is not a "
                             "verdict about a source, so it is retried rather than "
                             "recorded as a source without captions.")
    parser.add_argument("--retry-backoff", type=float, default=60.0,
                        help="seconds to rest before each retry pass")
    parser.add_argument("--pause-seconds", type=float, default=0.0,
                        help="wait between candidates. A 200-source burst gets "
                             "throttled by the provider, and a throttled caption "
                             "request looks exactly like a source with no captions, "
                             "so pacing protects the truth of the report.")
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
        read_source_candidates,
        write_manifest,
    )

    candidates = []
    for path in args.sources:
        if not path.is_file():
            print(f"source list not found: {path}", file=sys.stderr)
            return 2
        rows = read_source_candidates(path)
        candidates.extend(rows[: args.limit] if args.limit > 0 else rows)

    adapter_factory = None
    if args.offline_transcripts:
        from writing_coach.listening_source_import import OfflineTranscriptAdapter
        from writing_coach.media_recovery_policy import build_youtube_adapter as _live

        payload = json.loads(args.offline_transcripts.read_text(encoding="utf-8"))
        print(f"offline transcripts: {len(payload)} source(s) from "
              f"{args.offline_transcripts}")
        # Offline entries win; anything absent still goes to the live adapter,
        # so a partial handoff file is useful rather than all-or-nothing.
        adapter_factory = lambda: OfflineTranscriptAdapter(payload, _live())  # noqa: E731

    manifest, report = _run_with_retries(
        candidates,
        pause_seconds=args.pause_seconds,
        retry_passes=args.retry_passes,
        retry_backoff=args.retry_backoff,
        adapter_factory=adapter_factory,
    )
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
