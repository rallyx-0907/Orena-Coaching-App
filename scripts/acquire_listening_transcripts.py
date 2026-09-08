"""Acquire curated transcripts ONCE, and write them as a canonical handoff file.

This is the producer half of the offline ingestion path (D-046). It runs where
provider access works; `build_listening_dev_catalog.py --offline-transcripts`
then builds the catalog anywhere, including a host YouTube has IP-blocked.

    python scripts/acquire_listening_transcripts.py \\
        writing_coach/content/listening_sources_zh_pilot_daihuaxiyou.csv \\
        --out transcripts.json --limit 1

Acquisition order, stopping at the first that works, so the cheapest and most
faithful source wins:

    1. native provider captions   -> origin "provider_caption"
    2. Supadata                   -> origin "generated_asr"
    3. Groq ASR over a short-lived provider audio URL -> "generated_asr"

Rules this file exists to keep:

* Nothing is ever invented. A source that cannot be acquired is reported and
  skipped, never filled in with plausible text.
* Generated speech recognition is NEVER recorded as the provider's own
  captions, however it was obtained.
* Already-acquired transcripts are not re-acquired: the output file is merged,
  so re-running costs nothing for sources already present.

No media is downloaded or rehosted: Groq is handed a short-lived provider URL
and fetches it itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from writing_coach.media_providers.youtube import (  # noqa: E402
    canonical_youtube_url,
    parse_youtube_video_id,
)

PROVIDER_CAPTION = "provider_caption"
GENERATED_ASR = "generated_asr"


def _segments(rows) -> list[dict]:
    """Normalize to the canonical shape, dropping anything without real timing."""

    out: list[dict] = []
    for row in rows:
        text = " ".join(str(row["text"]).split())
        start, end = int(row["start_ms"]), int(row["end_ms"])
        if not text or end <= start:
            continue
        out.append({"start_ms": start, "end_ms": end, "original_text": text})
    return out


def from_native_captions(video_id: str, language: str) -> dict | None:
    from writing_coach.media_providers.youtube import PublicYouTubeCaptionClient

    track = PublicYouTubeCaptionClient().fetch_track(video_id, language)
    if track is None:
        return None
    rows = [
        {"text": s.text,
         "start_ms": int(float(s.start_seconds) * 1000),
         "end_ms": int((float(s.start_seconds) + float(s.duration_seconds)) * 1000)}
        for s in track.snippets
        if s.text and s.start_seconds is not None and s.duration_seconds is not None
    ]
    segments = _segments(rows)
    if not segments:
        return None
    return {"origin": PROVIDER_CAPTION, "language": track.source_language,
            "provider": "youtube", "model": "", "segments": segments}


def from_supadata(video_id: str, language: str) -> dict | None:
    from writing_coach.media_providers.supadata import SupadataTranscriptClient

    key = os.getenv("SUPADATA_API_KEY", "").strip()
    if not key:
        return None
    transcript = SupadataTranscriptClient(key, max_wait_seconds=240).fetch(
        canonical_youtube_url(video_id), language, mode="auto")
    if transcript is None:
        return None
    segments = _segments([
        {"text": c.text, "start_ms": c.offset_ms, "end_ms": c.offset_ms + c.duration_ms}
        for c in transcript.chunks
    ])
    if not segments:
        return None
    # Supadata "auto" may return the video's own captions or a generated
    # transcript, and the response does not distinguish them. Recording the
    # flattering answer would risk presenting machine text as official
    # captions, so this stays generated_asr.
    return {"origin": GENERATED_ASR, "language": transcript.language,
            "provider": "supadata", "model": "", "segments": segments}


def from_groq_asr(video_id: str, language: str) -> dict | None:
    from writing_coach.media_providers.youtube_audio import YtDlpYouTubeAudioUrlResolver
    from writing_coach.speech_asr import GroqSpeechAsrProvider

    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        return None
    audio = YtDlpYouTubeAudioUrlResolver(timeout_seconds=60).resolve(
        canonical_youtube_url(video_id))
    provider = GroqSpeechAsrProvider(key, timeout_seconds=180)
    result = provider.transcribe_url(audio.url, language=language or None)
    segments = _segments([
        {"text": s.text, "start_ms": s.start_ms, "end_ms": s.end_ms}
        for s in result.segments
    ])
    if not segments:
        return None
    return {"origin": GENERATED_ASR, "language": result.language or language,
            "provider": result.provider, "model": result.model, "segments": segments}


ACQUIRERS = (
    ("native-captions", from_native_captions),
    ("supadata", from_supadata),
    ("groq-asr", from_groq_asr),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path, help="source list CSV files")
    parser.add_argument("--out", type=Path, required=True,
                        help="handoff JSON, merged if it already exists")
    parser.add_argument("--limit", type=int, default=0,
                        help="acquire at most N new transcripts (0 = all)")
    parser.add_argument("--only", default="",
                        help="comma-separated candidate_ids to acquire")
    args = parser.parse_args()

    existing: dict = {}
    if args.out.is_file():
        existing = json.loads(args.out.read_text(encoding="utf-8"))
        print(f"{len(existing)} transcript(s) already acquired; they are not re-acquired")

    wanted = {item.strip() for item in args.only.split(",") if item.strip()}
    rows: list[dict[str, str]] = []
    for path in args.sources:
        rows.extend(csv.DictReader(path.open(encoding="utf-8-sig")))

    acquired = 0
    for row in rows:
        candidate_id = row["candidate_id"]
        if wanted and candidate_id not in wanted:
            continue
        try:
            video_id = parse_youtube_video_id(row["source_url"])
        except Exception:
            print(f"{candidate_id:<14} SKIP  unusable url")
            continue
        if video_id in existing:
            continue
        if args.limit and acquired >= args.limit:
            break

        language = row["language"].strip().casefold()
        for name, acquire in ACQUIRERS:
            try:
                entry = acquire(video_id, language)
            except Exception as exc:
                print(f"{candidate_id:<14} {name:<16} {type(exc).__name__}")
                continue
            if not entry:
                print(f"{candidate_id:<14} {name:<16} nothing returned")
                continue
            entry["title"] = row.get("title", "")
            entry["creator"] = row.get("source_family", "")
            existing[video_id] = entry
            acquired += 1
            print(f"{candidate_id:<14} {name:<16} OK {len(entry['segments'])} segments "
                  f"origin={entry['origin']}")
            break
        else:
            print(f"{candidate_id:<14} UNACQUIRED - reported, never invented")

    args.out.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"\nwrote {args.out} with {len(existing)} transcript(s); {acquired} new")
    return 0 if existing else 1


if __name__ == "__main__":
    raise SystemExit(main())
