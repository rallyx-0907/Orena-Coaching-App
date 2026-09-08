"""Group the L3 recovery-required candidates by WHY they have no usable captions.

The import report says a source is `RECOVERY_REQUIRED`. That is the right
product answer - playable media awaiting transcript recovery - but it is not a
useful answer for a human deciding what to do with a source pack. "Captions are
switched off by the uploader" and "this Chinese channel publishes English
subtitles only" need completely different responses, and only one of them is
fixable by editing the CSV.

Read-only: lists caption tracks, fetches nothing, spends no paid quota.

    python scripts/audit_listening_source_captions.py --report l3_import_report.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.media_providers.youtube import parse_youtube_video_id  # noqa: E402

# Why a candidate has no transcript in its own learning language.
DISABLED = "captions_disabled_by_uploader"
OTHER_LANGUAGE_ONLY = "captions_only_in_other_languages"
GENERATED_OTHER = "auto_captions_but_not_in_learning_language"
UNAVAILABLE = "video_unavailable"
PROBE_FAILED = "probe_failed"
HAS_TRACK = "has_track_in_learning_language"


def source_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def classify(api, video_id: str, language: str) -> tuple[str, list[str]]:
    from youtube_transcript_api._errors import (
        AgeRestricted,
        InvalidVideoId,
        NoTranscriptFound,
        TranscriptsDisabled,
        VideoUnavailable,
        VideoUnplayable,
    )

    try:
        listing = api.list(video_id)
    except TranscriptsDisabled:
        return DISABLED, []
    except (VideoUnavailable, VideoUnplayable, AgeRestricted, InvalidVideoId):
        return UNAVAILABLE, []
    except NoTranscriptFound:
        return OTHER_LANGUAGE_ONLY, []
    except Exception as exc:  # a probe failure is not a source verdict
        return PROBE_FAILED, [type(exc).__name__]

    codes = [str(getattr(item, "language_code", "")) for item in listing]
    wanted = [code for code in codes if code.split("-", 1)[0].casefold() == language]
    if wanted:
        return HAS_TRACK, codes
    if any(getattr(item, "is_generated", False) for item in listing):
        return GENERATED_OTHER, codes
    return OTHER_LANGUAGE_ONLY, codes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True,
                        help="the JSON report produced by build_listening_dev_catalog.py")
    parser.add_argument("--out", type=Path, default=None, help="write the audit as JSON")
    parser.add_argument("--outcome", default="RECOVERY_REQUIRED",
                        help="which outcome class to audit")
    args = parser.parse_args()

    from youtube_transcript_api import YouTubeTranscriptApi

    report = json.loads(args.report.read_text(encoding="utf-8"))
    wanted_ids = {
        entry["candidate_id"] for entry in report["entries"]
        if entry["outcome"] == args.outcome
    }

    rows = (source_rows(ROOT / "writing_coach/content/listening_sources_en_dev_100.csv")
            + source_rows(ROOT / "writing_coach/content/listening_sources_zh_dev_100.csv"))
    api = YouTubeTranscriptApi()

    findings: list[dict[str, object]] = []
    counts: Counter = Counter()
    for row in rows:
        if row["candidate_id"] not in wanted_ids:
            continue
        language = row["language"].strip().casefold()
        try:
            video_id = parse_youtube_video_id(row["source_url"])
        except Exception:
            reason, codes = PROBE_FAILED, ["malformed url"]
        else:
            reason, codes = classify(api, video_id, language)
        counts[(language, reason)] += 1
        findings.append({
            "candidate_id": row["candidate_id"],
            "language": language,
            "title": row["title"],
            "reason": reason,
            "available_caption_languages": codes[:10],
        })
        print(f"{row['candidate_id']:>8}  {reason:<38} {','.join(codes[:5])}", flush=True)

    grouped: dict[str, dict[str, int]] = {}
    for (language, reason), count in counts.items():
        grouped.setdefault(language, {})[reason] = count
    print("\n" + json.dumps(grouped, indent=2))

    if args.out:
        args.out.write_text(
            json.dumps({"grouped": grouped, "findings": findings},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
