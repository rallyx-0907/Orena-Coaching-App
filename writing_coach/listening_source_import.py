"""Deterministic development source importer for the Listening catalog.

LISTENING_PRODUCT_SPEC 5 and 6. Humans edit a CSV source list; this turns it
into the same catalog manifest shape the base catalog uses, reusing the existing
YouTube provider adapter, its caption/transcript normalization and the canonical
Media Learning Object. It builds no second importer and downloads no media.

Two rules shape everything here:

* Excerpt boundaries are never invented. Every excerpt starts and ends on a real
  transcript segment boundary produced by the provider, so a generated lesson
  can only claim timing the source actually has.
* Identities are deterministic. The same input row produces the same
  source_media_id, lesson_id and segment ids on every run, so re-importing does
  not churn learner progress that points at them.

A candidate that fails is reported and skipped. One bad URL must not cost the
rest of the batch.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from writing_coach.media_ingestion import (
    MediaAcquisition,
    ProviderRequestFailed,
    ProviderSourceUnavailable,
    ProviderTimedOut,
    ProviderTranscriptMalformed,
    ProviderUrlMalformed,
)
from writing_coach.listening_dev_artifact import (
    GENERATOR,
    GENERATOR_VERSION,
    file_digest,
    manifest_content_hash,
)
from writing_coach.listening_catalog import (
    CURATION_PROPOSED,
    DEV_CONTENT_STATUS,
    EN_LEVELS,
    PRACTICE_MODES,
    ZH_LEVELS,
)
from writing_coach.media_providers.youtube import (
    canonical_youtube_url,
    parse_youtube_video_id,
    recognizes_youtube_url,
)

SUPPORTED_LANGUAGES = frozenset({"en", "zh"})
DEFAULT_MIN_EXCERPT_SECONDS = 20
DEFAULT_MAX_EXCERPT_SECONDS = 90
DEFAULT_EXCERPT_COUNT = 3

# Outcomes the spec asks the report to distinguish.
ACCEPTED = "ACCEPTED"
SKIPPED = "SKIPPED"
FAILED = "FAILED"
DUPLICATE = "DUPLICATE"
MISSING_TRANSCRIPT = "MISSING_TRANSCRIPT"
UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
MEDIA_UNAVAILABLE = "MEDIA_UNAVAILABLE"

# The CSV category vocabulary, mapped onto the catalog's own topic vocabulary so
# generated lessons land in the discovery rails the spec names in 3.4.
CATEGORY_TOPICS: Mapping[str, str] = {
    "conversation": "conversations",
    "street-interview": "conversations",
    "daily-life": "daily-life",
    "story": "stories",
    "stories": "stories",
    "animation": "animation",
    "movie": "movie",
    "film": "movie",
    "drama": "movie",
    "podcast": "podcast",
    "interview": "interview",
    "science": "science",
    "technology": "technology",
    "culture": "culture",
    "travel": "travel",
    "kids": "kids",
    "family": "kids",
    "motivation": "stories",
    "education": "science",
}

EN_LEVEL_FALLBACK = "B1"
ZH_LEVEL_FALLBACK = "HSK3"

MIN_EXCERPT_FLOOR_SECONDS = 5
MAX_EXCERPT_CEILING_SECONDS = 600


def validate_candidate(candidate: SourceCandidate) -> str:
    """Why this row cannot be imported, or "" when it is usable.

    The human-editable columns are checked here, before anything reaches the
    manifest. A bad level or mode must cost that one candidate a report entry,
    not produce a manifest that load_catalog_manifest() later rejects whole.
    """

    if candidate.language not in SUPPORTED_LANGUAGES:
        return f"unsupported language {candidate.language or '(blank)'!s}"

    levels = EN_LEVELS if candidate.language == "en" else ZH_LEVELS
    if candidate.level_hint and candidate.level_hint.strip().upper() not in levels:
        return f"level_hint {candidate.level_hint!r} is not a {candidate.language.upper()} level"

    unknown_modes = [mode for mode in candidate.preferred_modes if _normalize_mode(mode) not in PRACTICE_MODES]
    if unknown_modes:
        return f"preferred_modes {unknown_modes!r} are not practice modes"

    if not 0 < candidate.min_excerpt_seconds <= candidate.max_excerpt_seconds:
        return (f"excerpt range {candidate.min_excerpt_seconds}-{candidate.max_excerpt_seconds}s "
                "is not an increasing positive range")
    if candidate.min_excerpt_seconds < MIN_EXCERPT_FLOOR_SECONDS:
        return f"min_excerpt_seconds {candidate.min_excerpt_seconds} is below {MIN_EXCERPT_FLOOR_SECONDS}"
    if candidate.max_excerpt_seconds > MAX_EXCERPT_CEILING_SECONDS:
        return f"max_excerpt_seconds {candidate.max_excerpt_seconds} is above {MAX_EXCERPT_CEILING_SECONDS}"
    if candidate.desired_excerpt_count <= 0:
        return f"desired_excerpt_count {candidate.desired_excerpt_count} must be positive"

    if not candidate.title.strip() and not candidate.category.strip():
        return "row has neither a title nor a category to describe it"
    return ""


def _normalize_mode(mode: str) -> str:
    # The CSV uses the learner-facing word "follow" for what the catalog calls
    # "listen"; everything else must already be a real practice mode.
    cleaned = mode.strip().casefold()
    return "listen" if cleaned == "follow" else cleaned


@dataclass(frozen=True)
class SourceCandidate:
    """One human-edited row of the development source list."""

    candidate_id: str
    language: str
    category: str
    source_family: str
    title: str
    source_url: str
    desired_excerpt_count: int
    min_excerpt_seconds: int
    max_excerpt_seconds: int
    preferred_modes: tuple[str, ...]
    level_hint: str
    notes: str


@dataclass
class ImportReport:
    """Per-outcome counts plus the reason each candidate landed where it did."""

    counts: Counter = field(default_factory=Counter)
    entries: list[dict[str, str]] = field(default_factory=list)
    generated_sources: int = 0
    generated_lessons: int = 0

    def record(self, candidate_id: str, outcome: str, detail: str = "") -> None:
        self.counts[outcome] += 1
        self.entries.append({"candidate_id": candidate_id, "outcome": outcome, "detail": detail})

    def as_dict(self) -> dict[str, Any]:
        return {
            "ACCEPTED": self.counts[ACCEPTED],
            "SKIPPED": self.counts[SKIPPED],
            "FAILED": self.counts[FAILED],
            "DUPLICATE": self.counts[DUPLICATE],
            "MISSING_TRANSCRIPT": self.counts[MISSING_TRANSCRIPT],
            "UNSUPPORTED_LANGUAGE": self.counts[UNSUPPORTED_LANGUAGE],
            "MEDIA_UNAVAILABLE": self.counts[MEDIA_UNAVAILABLE],
            "GENERATED_SOURCES": self.generated_sources,
            "GENERATED_LESSONS": self.generated_lessons,
            "entries": list(self.entries),
        }


def _int_or(value: Any, fallback: int) -> int:
    text = str(value or "").strip()
    if not text:
        return fallback
    # "1-3" means at most three; take the upper bound the editor allowed.
    if "-" in text:
        text = text.rsplit("-", 1)[-1].strip()
    try:
        parsed = int(text)
    except ValueError:
        return fallback
    return parsed if parsed > 0 else fallback


def read_source_candidates(path: Path) -> list[SourceCandidate]:
    """Parse a human-edited source CSV. Unknown columns are ignored."""

    # The pack ships with a BOM; utf-8-sig keeps the first header name clean.
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    candidates: list[SourceCandidate] = []
    for index, row in enumerate(rows):
        cleaned = {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        source_url = cleaned.get("source_url", "")
        if not source_url:
            continue
        candidates.append(SourceCandidate(
            candidate_id=cleaned.get("candidate_id") or f"row-{index + 1:03d}",
            language=cleaned.get("language", "").casefold(),
            category=cleaned.get("category", "").casefold(),
            source_family=cleaned.get("source_family", ""),
            title=cleaned.get("title", ""),
            source_url=source_url,
            desired_excerpt_count=_int_or(cleaned.get("desired_excerpt_count"), DEFAULT_EXCERPT_COUNT),
            min_excerpt_seconds=_int_or(cleaned.get("min_excerpt_seconds"), DEFAULT_MIN_EXCERPT_SECONDS),
            max_excerpt_seconds=_int_or(cleaned.get("max_excerpt_seconds"), DEFAULT_MAX_EXCERPT_SECONDS),
            preferred_modes=tuple(m for m in cleaned.get("preferred_modes", "").split("|") if m),
            level_hint=cleaned.get("level_hint", ""),
            notes=cleaned.get("notes", ""),
        ))
    return candidates


def plan_excerpts(
    segments: Sequence[Mapping[str, Any]],
    *,
    min_seconds: int,
    max_seconds: int,
    limit: int,
) -> list[tuple[int, int]]:
    """Group real transcript segments into excerpt windows.

    Every boundary returned is a boundary the transcript already had. Segments
    are packed in order until the window would exceed `max_seconds`, and the
    window is kept only once it reaches `min_seconds`, so an excerpt is never
    stretched or trimmed to hit a target length.

    Windows are then spread across the source rather than taken from the front,
    because the opening seconds of a video are usually titles and intros.
    """

    if not segments:
        return []
    minimum, maximum = min_seconds * 1000, max_seconds * 1000
    windows: list[tuple[int, int]] = []
    start: int | None = None
    end = 0
    for segment in segments:
        seg_start, seg_end = int(segment["start_ms"]), int(segment["end_ms"])
        if start is None:
            start, end = seg_start, seg_end
            continue
        if seg_end - start > maximum:
            if end - start >= minimum:
                windows.append((start, end))
            start, end = seg_start, seg_end
            continue
        end = seg_end
    if start is not None and end - start >= minimum:
        windows.append((start, end))

    if len(windows) <= limit:
        return windows
    # Even spread, first window always included, order preserved.
    step = len(windows) / limit
    picked = sorted({min(len(windows) - 1, int(i * step)) for i in range(limit)})
    return [windows[i] for i in picked]


def _segments_of(acquisition: MediaAcquisition) -> list[dict[str, Any]]:
    transcript = acquisition.media_object.transcript
    if transcript is None:
        return []
    return [
        {
            "segment_id": segment.segment_id,
            "order": segment.order,
            "start_ms": int(segment.start_ms),
            "end_ms": int(segment.end_ms),
            "original_text": segment.original_text,
        }
        for segment in transcript.segments
    ]


def youtube_poster_url(video_id: str) -> str:
    """The provider's own thumbnail, not a copy we host."""

    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _poster_for(provider_thumbnail: str, video_id: str) -> str:
    """Prefer the provider's advertised thumbnail, fall back to the known path.

    oEmbed returns a thumbnail on i.ytimg.com; if it ever returns something the
    catalog boundary would reject, the deterministic path is used instead of
    letting the whole source fail over a decoration.
    """

    cleaned = str(provider_thumbnail or "").strip()
    if cleaned.startswith("https://i.ytimg.com/") or cleaned.startswith("https://img.youtube.com/"):
        return cleaned
    return youtube_poster_url(video_id)


def _provider_metadata(adapter: Any, canonical_url: str) -> Any:
    """The adapter's own metadata when it exposes it, empty otherwise.

    Reuses the existing oEmbed path rather than adding a second metadata call,
    and degrades quietly: missing creator metadata must not fail an import that
    already has playback and a transcript.
    """

    from writing_coach.media_providers.youtube import YouTubeSourceMetadata

    client = getattr(adapter, "_metadata_client", None)
    fetch = getattr(client, "fetch_metadata", None)
    if fetch is None:
        return YouTubeSourceMetadata(title="")
    try:
        return fetch(canonical_url)
    except Exception:
        return YouTubeSourceMetadata(title="")


def source_media_id(video_id: str) -> str:
    """Deterministic from the canonical video identity, nothing else."""

    return f"youtube-{video_id}"


def lesson_id_for(language: str, video_id: str, excerpt_start_ms: int) -> str:
    """Provisional identity for a generated excerpt, anchored on start time.

    Start time survives re-segmentation better than a segment ordinal does: if
    the provider reshapes auto-captions into more or fewer cues, a window that
    still begins at the same second keeps its id, whereas every ordinal after
    the change would shift.

    It is still PROVISIONAL. If the provider re-times captions the id can
    change, so this must not be described as permanently stable. A curator
    promoting an excerpt should assign a durable editorial id at that point;
    that identity is a curation concern, not a generator one.
    """

    return f"dev-{language}-{video_id}-t{excerpt_start_ms // 1000:05d}"


def _level_for(candidate: SourceCandidate) -> str:
    if candidate.level_hint:
        return candidate.level_hint.strip().upper()
    return EN_LEVEL_FALLBACK if candidate.language == "en" else ZH_LEVEL_FALLBACK


def _topic_for(candidate: SourceCandidate) -> str:
    return CATEGORY_TOPICS.get(candidate.category, candidate.category or "conversations")


def build_dev_catalog(
    candidates: Iterable[SourceCandidate],
    adapter: Any,
    report: ImportReport | None = None,
) -> tuple[dict[str, Any], ImportReport]:
    """Run the pipeline over a candidate list and return a catalog manifest.

    EN and ZH go through exactly this function; nothing branches on language
    except the level vocabulary and the topic the editor chose.
    """

    outcome = report or ImportReport()
    sources: list[dict[str, Any]] = []
    lessons: list[dict[str, Any]] = []
    seen_videos: set[str] = set()

    for candidate in candidates:
        if candidate.language not in SUPPORTED_LANGUAGES:
            outcome.record(candidate.candidate_id, UNSUPPORTED_LANGUAGE, candidate.language or "(blank)")
            continue
        # Human-editable fields are checked before generation, so a bad level or
        # mode costs this one row rather than the whole overlay.
        invalid = validate_candidate(candidate)
        if invalid:
            outcome.record(candidate.candidate_id, SKIPPED, invalid)
            continue
        if not recognizes_youtube_url(candidate.source_url):
            outcome.record(candidate.candidate_id, SKIPPED, "not a supported provider URL")
            continue
        try:
            video_id = parse_youtube_video_id(candidate.source_url)
        except ProviderUrlMalformed:
            outcome.record(candidate.candidate_id, SKIPPED, "malformed provider URL")
            continue
        if video_id in seen_videos:
            outcome.record(candidate.candidate_id, DUPLICATE, video_id)
            continue

        try:
            acquisition = adapter.acquire(canonical_youtube_url(video_id), candidate.language)
        except ProviderTranscriptMalformed as exc:
            outcome.record(candidate.candidate_id, MISSING_TRANSCRIPT, type(exc).__name__)
            continue
        except (ProviderSourceUnavailable, ProviderTimedOut, ProviderRequestFailed) as exc:
            outcome.record(candidate.candidate_id, MEDIA_UNAVAILABLE, type(exc).__name__)
            continue
        except Exception as exc:  # one bad candidate must not end the batch
            outcome.record(candidate.candidate_id, FAILED, f"{type(exc).__name__}: {exc}"[:160])
            continue

        segments = _segments_of(acquisition)
        if not segments:
            outcome.record(candidate.candidate_id, MISSING_TRANSCRIPT, "no transcript segments")
            continue

        windows = plan_excerpts(
            segments,
            min_seconds=candidate.min_excerpt_seconds,
            max_seconds=candidate.max_excerpt_seconds,
            limit=candidate.desired_excerpt_count,
        )
        if not windows:
            outcome.record(candidate.candidate_id, SKIPPED, "no excerpt reaches the minimum length")
            continue

        seen_videos.add(video_id)
        asset = acquisition.media_object.asset
        provider_meta = _provider_metadata(adapter, asset.source_url)
        duration_ms = max(int(segment["end_ms"]) for segment in segments)
        topic = _topic_for(candidate)
        level = _level_for(candidate)
        modes = list(candidate.preferred_modes or ("listen", "active", "dictation", "shadowing"))
        modes = ["listen" if mode == "follow" else mode for mode in modes]
        if "listen" not in modes:
            modes.insert(0, "listen")

        sources.append({
            "source_media_id": source_media_id(video_id),
            "source_url": acquisition.media_object.asset.source_url,
            "source_provider": "youtube",
            "source_type": "external-video",
            # The provider owns source identity; the CSV only fills gaps.
            "source_title": asset.title or candidate.title or video_id,
            "source_creator": provider_meta.author_name or candidate.source_family or "YouTube",
            "language": candidate.language,
            "duration_ms": duration_ms,
            "playback": {
                "provider": acquisition.playback.provider,
                "kind": acquisition.playback.kind,
                "url": acquisition.playback.url,
            },
            "poster_url": _poster_for(provider_meta.thumbnail_url, video_id),
            "rights": {
                # Unreviewed by definition, so it says so. Claiming "verified"
                # to satisfy the base loader would make the catalog lie about
                # its own review state, and the base loader now refuses this.
                "license_name": "Provider terms (development candidate)",
                "license_url": "https://www.youtube.com/t/terms",
                "provenance_url": asset.source_url,
                "allowed_usage_type": "development-embed-only",
                "review_status": "rights_review",
            },
            "segments": segments,
        })
        outcome.generated_sources += 1

        for start_ms, end_ms in windows:
            lessons.append({
                "lesson_id": lesson_id_for(candidate.language, video_id, start_ms),
                "source_media_id": source_media_id(video_id),
                "excerpt_start_ms": start_ms,
                "excerpt_end_ms": end_ms,
                "title": candidate.title or asset.title or video_id,
                "description": candidate.notes or f"Development excerpt from {asset.title or video_id}.",
                "topic": topic,
                "subtopics": [candidate.category] if candidate.category else [],
                "tags": [tag for tag in (candidate.category, "dev-candidate") if tag],
                "estimated_level": level,
                "reviewed_level": None,
                "level_evidence": {
                    "source": "importer-estimate",
                    "review_note": "Development candidate. Level, excerpt boundary, translation and Pinyin are all unreviewed.",
                },
                "available_modes": modes,
                "status": DEV_CONTENT_STATUS,
                # A window that met a length rule is a proposal. Only a curator
                # promotes it, and the loader refuses a generator that tries.
                "curation_state": CURATION_PROPOSED,
                "artwork": topic,
                "vocabulary": [],
                "sections": ["new"],
            })
            outcome.generated_lessons += 1
        outcome.record(candidate.candidate_id, ACCEPTED, f"{len(windows)} excerpt(s)")

    manifest = {"schema_version": 1, "sources": sources, "lessons": lessons}
    return manifest, outcome


def write_manifest(
    manifest: Mapping[str, Any],
    path: Path,
    source_lists: Sequence[Path] = (),
) -> None:
    """Write the generated artifact with provenance and an integrity stamp.

    The artifact is committed rather than gitignored, so a clean checkout or a
    container rebuild still has the development catalog without regenerating it
    from the network at startup. Because it is committed it must also be
    tamper-evident: humans edit the CSV, never this file, and the content hash
    is what turns that from a comment into something the loader can check.

    Input CSVs are recorded by digest so a reviewer can tell which source lists
    a snapshot came from.
    """

    payload = dict(manifest)
    payload["generated_by"] = GENERATOR
    payload["generator_version"] = GENERATOR_VERSION
    payload["do_not_edit"] = "Generated file. Edit the source CSV and regenerate."
    payload["source_lists"] = [
        {"name": item.name, "sha256": file_digest(item)}
        for item in source_lists if item.is_file()
    ]
    # Over the payload, not the bare manifest: the fingerprint now covers the
    # provenance header this function just added.
    payload["content_hash"] = manifest_content_hash(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_candidates(paths: Iterable[Path]) -> Iterator[SourceCandidate]:
    for path in paths:
        yield from read_source_candidates(path)
