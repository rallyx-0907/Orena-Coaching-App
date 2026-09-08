"""Versioned, rights-aware Listening catalog over canonical Media Learning.

The manifest separates source media, canonical timestamped segments, and
learner-facing excerpts.  Curators can therefore add or revise content without
editing a React screen or creating a second player/transcript architecture.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from writing_coach.listening_dev_artifact import verify_manifest_integrity
from writing_coach.media_ingestion import MediaPlayback
from writing_coach.core.deployment import TIER_PREVIEW, resolve_deployment_tier
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    SegmentTranslation,
    TranscriptSegment,
)


CATALOG_MANIFEST = Path(__file__).with_name("content") / "listening_catalog.v1.json"
CONTENT_STATUSES = frozenset({"DRAFT", "PROCESSING", "NEEDS_REVIEW", "READY", "PUBLISHED", "ARCHIVED"})
# Generated development candidates get their own lifecycle rather than borrowing
# PUBLISHED/verified. They are unreviewed by definition, so claiming either would
# make the catalog lie about its own review state; the base loader refuses them
# and only the development overlay may carry them.
DEV_CONTENT_STATUS = "DEV_CANDIDATE"
DEV_CONTENT_STATUSES = frozenset({DEV_CONTENT_STATUS})
DEV_RIGHTS_STATUSES = frozenset({"rights_review", "content_review"})
VERIFIED_RIGHTS_STATUS = "verified"
# A generated excerpt is a proposal until a curator looks at it. Packing captions
# into a length window is not evidence of a natural pedagogical boundary.
CURATION_PROPOSED = "proposed"
CURATION_REVIEWED = "reviewed"
CURATION_STATES = frozenset({CURATION_PROPOSED, CURATION_REVIEWED})
# Media and posters may only come from origins the rights review actually
# covered. media-player.js and the native adapter enforce the same list at the
# edge; validating here means an editorial pipeline cannot introduce a source
# the players would then have to reject.
REVIEWED_MEDIA_HOSTS = frozenset({"commons.wikimedia.org", "upload.wikimedia.org"})
# A poster is published by the same provider as the media it depicts, so the
# allowlist is per provider rather than one global set: a YouTube lesson's
# thumbnail legitimately comes from YouTube's image CDN, and a Commons lesson's
# never does. The web player and the native adapter apply the same mapping.
REVIEWED_POSTER_HOSTS: Mapping[str, frozenset[str]] = {
    "wikimedia-commons": REVIEWED_MEDIA_HOSTS,
    "youtube": frozenset({"i.ytimg.com", "img.youtube.com"}),
}
PUBLIC_CONTENT_STATUS = "PUBLISHED"
EN_LEVELS = frozenset({"A1", "A2", "B1", "B2", "C1", "C2"})
ZH_LEVELS = frozenset({"HSK1", "HSK2", "HSK3", "HSK4", "HSK5", "HSK6", "HSK7-9"})
PRACTICE_MODES = frozenset({"listen", "active", "dictation", "shadowing"})

# LISTENING_PRODUCT_SPEC 3.4. Topical rails are DERIVED from a lesson's topic and
# tags rather than hand-listed per lesson, so the bulk source importer (L2) can
# add content without an editor maintaining section membership by hand. A lesson
# may still name a section explicitly; the two are merged.
DISCOVERY_TOPIC_SECTIONS: tuple[tuple[str, frozenset[str]], ...] = (
    ("movie-animation", frozenset({"animation", "movie", "movies", "film", "drama", "series", "trailer", "cartoon"})),
    ("daily-conversations", frozenset({"daily-life", "conversation", "conversations", "social-life"})),
    ("stories", frozenset({"story", "stories", "narrative", "storytelling"})),
    ("podcast-interview", frozenset({"podcast", "interview", "interviews", "talk"})),
    ("science-technology", frozenset({"science", "technology", "tech", "documentary", "how-to"})),
    ("culture", frozenset({"culture", "history", "travel"})),
    ("kids-family", frozenset({"kids", "family", "family-friendly", "children"})),
)

# A lesson short enough to finish in one sitting. The spec asks for a Quick
# Practice rail; deriving it from real duration beats trusting a hand-typed tag.
QUICK_PRACTICE_MAX_MS = 90_000


# How a persisted curated transcript came to exist, and how far it has been
# checked. These travel with the transcript so nothing downstream has to guess.
TRANSCRIPT_ORIGIN_PROVIDER_CAPTION = "provider_caption"
TRANSCRIPT_ORIGIN_GENERATED_ASR = "generated_asr"
TRANSCRIPT_ORIGIN_UNSPECIFIED = "unspecified"

TRANSCRIPT_QUALITY_PROVIDER_CAPTION = "provider_caption"
TRANSCRIPT_QUALITY_GENERATED_UNREVIEWED = "generated_unreviewed"
TRANSCRIPT_QUALITY_REVIEWED = "reviewed"
TRANSCRIPT_QUALITY_UNSPECIFIED = "unspecified"

TRANSCRIPT_ORIGINS = frozenset({
    TRANSCRIPT_ORIGIN_PROVIDER_CAPTION,
    TRANSCRIPT_ORIGIN_GENERATED_ASR,
    TRANSCRIPT_ORIGIN_UNSPECIFIED,
})
TRANSCRIPT_QUALITY_STATES = frozenset({
    TRANSCRIPT_QUALITY_PROVIDER_CAPTION,
    TRANSCRIPT_QUALITY_GENERATED_UNREVIEWED,
    TRANSCRIPT_QUALITY_REVIEWED,
    TRANSCRIPT_QUALITY_UNSPECIFIED,
})


@dataclass(frozen=True)
class CatalogSource:
    source_media_id: str
    source_url: str
    source_provider: str
    source_type: str
    source_title: str
    source_creator: str
    language: str
    duration_ms: int
    playback: MediaPlayback
    license_name: str
    license_url: str
    provenance_url: str
    allowed_usage_type: str
    rights_review_status: str
    segments: tuple[Mapping[str, Any], ...]
    poster_url: str = ""
    # Transcript provenance. A curated transcript is acquired once at ingestion
    # and persisted here, so a learner never waits on a provider - but a
    # persisted transcript must still say what it is. The defaults are
    # deliberately UNSPECIFIED rather than "provider_caption": an older lesson
    # that predates this field has an unknown origin, and guessing the
    # flattering answer would let generated text pass as official captions.
    transcript_origin: str = TRANSCRIPT_ORIGIN_UNSPECIFIED
    transcript_revision: int = 1
    transcript_language: str = ""
    transcript_quality_state: str = TRANSCRIPT_QUALITY_UNSPECIFIED
    transcript_provider: str = ""
    transcript_model: str = ""

    @property
    def transcript_is_generated(self) -> bool:
        return self.transcript_origin == TRANSCRIPT_ORIGIN_GENERATED_ASR

    @property
    def transcript_is_reviewed(self) -> bool:
        return self.transcript_quality_state == TRANSCRIPT_QUALITY_REVIEWED


@dataclass(frozen=True)
class CuratedListeningLesson:
    lesson_id: str
    source: CatalogSource
    media_object: MediaLearningObject
    playback: MediaPlayback
    excerpt_start_ms: int
    excerpt_end_ms: int
    description: str
    topic: str
    subtopics: tuple[str, ...]
    estimated_level: str
    reviewed_level: str | None
    level_evidence: Mapping[str, str]
    available_modes: tuple[str, ...]
    content_status: str
    curation_state: str
    content_tags: tuple[str, ...]
    sections: tuple[str, ...]
    vocabulary: tuple[str, ...] = ()
    artwork: str = "listen"

    @property
    def duration_ms(self) -> int:
        return self.excerpt_end_ms - self.excerpt_start_ms

    @property
    def level(self) -> str:
        return self.reviewed_level or self.estimated_level

    @property
    def speech_speed(self) -> str | None:
        return self.level_evidence.get("speech_speed")

    @property
    def pinyin_by_segment(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (str(segment["segment_id"]), str(segment.get("pinyin") or ""))
            for segment in self.source.segments
            if segment.get("pinyin") and _segment_in_excerpt(segment, self.excerpt_start_ms, self.excerpt_end_ms)
        )


def _playback_url(playback: Mapping[str, Any], source_id: str) -> str:
    """Direct audio/video must be rights-reviewed; embeds keep provider rules."""

    url = _required_text(playback.get("url"), "playback url")
    if str(playback.get("kind") or "").strip() in {"audio", "video"}:
        return _reviewed_media_url(url, "playback url", source_id)
    return url


def _reviewed_media_url(
    value: Any,
    field: str,
    source_id: str,
    hosts: frozenset[str] = REVIEWED_MEDIA_HOSTS,
) -> str:
    """An https URL on a rights-reviewed host, or a hard failure."""

    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    parsed = urlsplit(cleaned)
    # `hostname` alone is not the policy: userinfo and a port both survive it,
    # so `https://user:pass@upload.wikimedia.org/x` would report an allowlisted
    # host here while the web and native clients reject it. The server, the web
    # player and the native adapter all apply exactly these four rules.
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username
        or parsed.password
        or parsed.port is not None
    ):
        raise ValueError(
            f"Listening source {source_id} {field} must be an https URL, with no credentials "
            f"or port, on a rights-reviewed host."
        )
    return cleaned


def _required_text(value: Any, field: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"Listening catalog {field} must not be empty.")
    return cleaned


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Listening catalog {field} must be a list.")
    items = tuple(_required_text(item, field) for item in value)
    if len(items) != len(set(items)):
        raise ValueError(f"Listening catalog {field} contains duplicates.")
    return items


def _transcript_provenance(
    raw: Any,
    source_id: str,
    language: str,
) -> dict[str, Any]:
    """Read the optional transcript provenance block.

    Optional on purpose: lessons written before this existed stay loadable and
    are reported as UNSPECIFIED rather than being silently upgraded to
    "official captions". An unknown vocabulary value is rejected rather than
    passed through, so a typo cannot invent a quality state.
    """

    if raw is None:
        return {"transcript_language": language}
    if not isinstance(raw, Mapping):
        raise ValueError(f"Listening source {source_id} has a malformed transcript block.")

    origin = str(raw.get("origin") or TRANSCRIPT_ORIGIN_UNSPECIFIED).strip().casefold()
    quality = str(raw.get("quality_state") or TRANSCRIPT_QUALITY_UNSPECIFIED).strip().casefold()
    if origin not in TRANSCRIPT_ORIGINS:
        raise ValueError(f"Listening source {source_id} has unknown transcript origin {origin!r}.")
    if quality not in TRANSCRIPT_QUALITY_STATES:
        raise ValueError(f"Listening source {source_id} has unknown transcript quality {quality!r}.")
    # Generated text may never be described as the provider's own captions.
    if origin == TRANSCRIPT_ORIGIN_GENERATED_ASR and quality == TRANSCRIPT_QUALITY_PROVIDER_CAPTION:
        raise ValueError(
            f"Listening source {source_id} labels generated ASR as provider captions.")

    try:
        revision = int(raw.get("revision", 1))
    except (TypeError, ValueError):
        raise ValueError(f"Listening source {source_id} has a malformed transcript revision.") from None
    if revision < 1:
        raise ValueError(f"Listening source {source_id} has a transcript revision below 1.")

    return {
        "transcript_origin": origin,
        "transcript_revision": revision,
        "transcript_language": str(raw.get("language") or language).strip() or language,
        "transcript_quality_state": quality,
        "transcript_provider": str(raw.get("provider") or "").strip(),
        "transcript_model": str(raw.get("model") or "").strip(),
    }


def _segment_in_excerpt(segment: Mapping[str, Any], start_ms: int, end_ms: int) -> bool:
    return int(segment["start_ms"]) >= start_ms and int(segment["end_ms"]) <= end_ms


def _load_source(raw: Mapping[str, Any], *, allow_dev: bool = False) -> CatalogSource:
    source_id = _required_text(raw.get("source_media_id"), "source_media_id")
    language = _required_text(raw.get("language"), "language").casefold()
    if language not in {"en", "zh"}:
        raise ValueError(f"Listening source {source_id} has unsupported language {language}.")
    duration_ms = int(raw.get("duration_ms") or 0)
    if duration_ms <= 0:
        raise ValueError(f"Listening source {source_id} has an invalid duration.")

    playback = raw.get("playback")
    rights = raw.get("rights")
    segments = raw.get("segments")
    if not isinstance(playback, Mapping) or not isinstance(rights, Mapping) or not isinstance(segments, list) or not segments:
        raise ValueError(f"Listening source {source_id} is missing playback, rights, or segments.")
    review_status = _required_text(rights.get("review_status"), "rights review_status")
    allowed_rights = {VERIFIED_RIGHTS_STATUS} | (DEV_RIGHTS_STATUSES if allow_dev else set())
    if review_status not in allowed_rights:
        raise ValueError(f"Listening source {source_id} has not passed rights review.")

    normalized_segments: list[Mapping[str, Any]] = []
    seen_segment_ids: set[str] = set()
    previous_end = -1
    for order, segment in enumerate(segments):
        if not isinstance(segment, Mapping):
            raise ValueError(f"Listening source {source_id} has an invalid segment.")
        segment_id = _required_text(segment.get("segment_id"), "segment_id")
        start_ms = int(segment.get("start_ms") or 0)
        end_ms = int(segment.get("end_ms") or 0)
        if segment_id in seen_segment_ids or start_ms < 0 or end_ms <= start_ms or end_ms > duration_ms or start_ms < previous_end:
            raise ValueError(f"Listening source {source_id} has invalid canonical segment timing.")
        seen_segment_ids.add(segment_id)
        previous_end = end_ms
        translations = segment.get("translations") or {}
        if not isinstance(translations, Mapping):
            raise ValueError(f"Listening segment {segment_id} has invalid translations.")
        normalized_segments.append({
            "segment_id": segment_id,
            "order": order,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "original_text": _required_text(segment.get("original_text"), "original_text"),
            "pinyin": str(segment.get("pinyin") or "").strip(),
            "translations": {str(key).casefold(): _required_text(value, "translation") for key, value in translations.items()},
        })

    return CatalogSource(
        source_media_id=source_id,
        source_url=_required_text(raw.get("source_url"), "source_url"),
        source_provider=_required_text(raw.get("source_provider"), "source_provider"),
        source_type=_required_text(raw.get("source_type"), "source_type"),
        source_title=_required_text(raw.get("source_title"), "source_title"),
        source_creator=_required_text(raw.get("source_creator"), "source_creator"),
        language=language,
        duration_ms=duration_ms,
        playback=MediaPlayback(
            _required_text(playback.get("provider"), "playback provider"),
            _required_text(playback.get("kind"), "playback kind"),
            _playback_url(playback, source_id),
        ),
        license_name=_required_text(rights.get("license_name"), "license_name"),
        license_url=_required_text(rights.get("license_url"), "license_url"),
        provenance_url=_required_text(rights.get("provenance_url"), "provenance_url"),
        allowed_usage_type=_required_text(rights.get("allowed_usage_type"), "allowed_usage_type"),
        rights_review_status=review_status,
        segments=tuple(normalized_segments),
        **_transcript_provenance(raw.get("transcript"), source_id, language),
        poster_url=_reviewed_media_url(
            raw.get("poster_url"),
            "poster_url",
            source_id,
            REVIEWED_POSTER_HOSTS.get(str(raw.get("source_provider") or "").strip(), REVIEWED_MEDIA_HOSTS),
        ),
    )


def discovery_sections(lesson: CuratedListeningLesson) -> tuple[str, ...]:
    """Every discovery rail this lesson belongs in, explicit plus derived.

    LISTENING_PRODUCT_SPEC 3.4 names the rails; 3.5 wants real playable media to
    lead. `popular` is deliberately never derived: there is no popularity signal
    in the repository, and the spec allows that rail only when real data exists.
    """

    sections: list[str] = [s for s in lesson.sections if s != "popular"]
    vocabulary = {lesson.topic, *lesson.subtopics, *lesson.content_tags}

    for section_id, matches in DISCOVERY_TOPIC_SECTIONS:
        if section_id not in sections and vocabulary & matches:
            sections.append(section_id)

    if "dictation" not in sections and "dictation" in lesson.available_modes:
        sections.append("dictation")
    if "shadowing" not in sections and "shadowing" in lesson.available_modes:
        sections.append("shadowing")
    if "quick-practice" not in sections and 0 < lesson.duration_ms <= QUICK_PRACTICE_MAX_MS:
        sections.append("quick-practice")
    # Seed audio is still practice, but it belongs in its own rail rather than
    # competing with real video for the first viewport.
    if lesson.playback.kind == "audio" and "audio-practice" not in sections:
        sections.append("audio-practice")

    return tuple(sections)


def is_real_media(lesson: CuratedListeningLesson) -> bool:
    """Real playable video with a real poster, as the spec means it in 3.5."""

    return lesson.playback.kind == "video" and bool(lesson.source.poster_url)


def discovery_rank(lesson: CuratedListeningLesson) -> tuple[int, int, str]:
    """Ordering inside a rail: real poster-backed video first, then stable.

    Spec 3.5: old audio seed lessons must not visually dominate the first
    viewport. Ties fall back to the lesson id so the order never wobbles
    between requests.
    """

    return (0 if is_real_media(lesson) else 1, 0 if lesson.source.poster_url else 1, lesson.lesson_id)


def _media_object(source: CatalogSource, title: str, start_ms: int, end_ms: int) -> MediaLearningObject:
    selected = tuple(segment for segment in source.segments if _segment_in_excerpt(segment, start_ms, end_ms))
    if not selected:
        raise ValueError(f"Listening excerpt {title} contains no complete canonical segment.")
    transcript = tuple(
        TranscriptSegment(
            str(segment["segment_id"]),
            int(segment["order"]),
            int(segment["start_ms"]),
            int(segment["end_ms"]),
            str(segment["original_text"]),
        )
        for segment in selected
    )
    translations = tuple(
        SegmentTranslation(str(segment["segment_id"]), language, text)
        for segment in selected
        for language, text in dict(segment["translations"]).items()
    )
    return MediaLearningObject(
        MediaLearningAsset(
            asset_id=source.source_media_id,
            source_url=source.source_url,
            source_provider=source.source_provider,
            source_type=source.source_type,
            title=title,
            source_language=source.language,
            processing_state=MediaProcessingState.READY,
            duration_ms=source.duration_ms,
            transcript_available=True,
            translation_available=bool(translations),
        ),
        MediaTranscript(source.source_media_id, source.language, transcript),
        translations,
    )


def load_catalog_manifest(
    path: Path = CATALOG_MANIFEST, *, allow_dev: bool = False,
) -> tuple[Mapping[str, CatalogSource], tuple[CuratedListeningLesson, ...]]:
    """Load a catalog manifest. `allow_dev` permits the development lifecycle.

    The base catalog is always loaded with allow_dev False, so an unreviewed
    development candidate cannot enter it however the file is edited.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1 or not isinstance(raw.get("sources"), list) or not isinstance(raw.get("lessons"), list):
        raise ValueError("Listening catalog manifest schema is unsupported.")

    source_list = tuple(_load_source(item, allow_dev=allow_dev) for item in raw["sources"])
    if len({item.source_media_id for item in source_list}) != len(source_list):
        raise ValueError("Listening catalog source identities must be unique.")
    sources = {item.source_media_id: item for item in source_list}

    lessons: list[CuratedListeningLesson] = []
    seen_lesson_ids: set[str] = set()
    for raw_lesson in raw["lessons"]:
        lesson_id = _required_text(raw_lesson.get("lesson_id"), "lesson_id")
        source_id = _required_text(raw_lesson.get("source_media_id"), "source_media_id")
        source = sources.get(source_id)
        if lesson_id in seen_lesson_ids or source is None:
            raise ValueError(f"Listening lesson {lesson_id} has a duplicate or unknown source.")
        seen_lesson_ids.add(lesson_id)

        status = _required_text(raw_lesson.get("status"), "status").upper()
        allowed_status = CONTENT_STATUSES | (DEV_CONTENT_STATUSES if allow_dev else frozenset())
        if status not in allowed_status:
            raise ValueError(f"Listening lesson {lesson_id} has invalid lifecycle status.")
        curation_state = str(raw_lesson.get("curation_state") or CURATION_REVIEWED).strip().casefold()
        if curation_state not in CURATION_STATES:
            raise ValueError(f"Listening lesson {lesson_id} has invalid curation state.")
        if status == DEV_CONTENT_STATUS and curation_state != CURATION_PROPOSED:
            # A dev candidate becomes `reviewed` only by a curator promoting it,
            # never by the generator asserting it about its own output.
            raise ValueError(f"Listening lesson {lesson_id} cannot self-declare curation review.")
        start_ms = int(raw_lesson.get("excerpt_start_ms") or 0)
        end_ms = int(raw_lesson.get("excerpt_end_ms") or 0)
        if start_ms < 0 or end_ms <= start_ms or end_ms > source.duration_ms:
            raise ValueError(f"Listening lesson {lesson_id} has invalid excerpt bounds.")

        estimated_level = _required_text(raw_lesson.get("estimated_level"), "estimated_level").upper()
        reviewed_raw = str(raw_lesson.get("reviewed_level") or "").strip().upper()
        reviewed_level = reviewed_raw or None
        allowed_levels = EN_LEVELS if source.language == "en" else ZH_LEVELS
        if estimated_level not in allowed_levels or (reviewed_level and reviewed_level not in allowed_levels):
            raise ValueError(f"Listening lesson {lesson_id} has an invalid canonical level.")
        evidence = raw_lesson.get("level_evidence")
        if not isinstance(evidence, Mapping) or not all(str(value).strip() for value in evidence.values()):
            raise ValueError(f"Listening lesson {lesson_id} lacks explainable level evidence.")

        modes = _string_tuple(raw_lesson.get("available_modes"), "available_modes")
        if not modes or not set(modes).issubset(PRACTICE_MODES) or "listen" not in modes:
            raise ValueError(f"Listening lesson {lesson_id} has invalid practice modes.")
        tags = _string_tuple(raw_lesson.get("tags"), "tags")
        if not tags:
            raise ValueError(f"Listening lesson {lesson_id} needs at least one discovery tag.")
        title = _required_text(raw_lesson.get("title"), "title")
        lesson = CuratedListeningLesson(
            lesson_id=lesson_id,
            source=source,
            media_object=_media_object(source, title, start_ms, end_ms),
            playback=source.playback,
            excerpt_start_ms=start_ms,
            excerpt_end_ms=end_ms,
            description=_required_text(raw_lesson.get("description"), "description"),
            topic=_required_text(raw_lesson.get("topic"), "topic"),
            subtopics=_string_tuple(raw_lesson.get("subtopics"), "subtopics"),
            estimated_level=estimated_level,
            reviewed_level=reviewed_level,
            level_evidence={str(key): str(value).strip() for key, value in evidence.items()},
            available_modes=modes,
            content_status=status,
            curation_state=curation_state,
            content_tags=tags,
            sections=_string_tuple(raw_lesson.get("sections"), "sections"),
            vocabulary=_string_tuple(raw_lesson.get("vocabulary"), "vocabulary"),
            artwork=_required_text(raw_lesson.get("artwork"), "artwork"),
        )
        lessons.append(lesson)
    return sources, tuple(lessons)





DEV_CATALOG_MANIFEST = Path(__file__).with_name("content") / "listening_catalog.dev.generated.json"
# The governed preview artifact. Same schema, same loader, same integrity check
# as every other catalog file - only its visibility differs. It is NOT the L3
# publication snapshot and does not flip SNAPSHOT_REQUIRED.
PREVIEW_CATALOG_MANIFEST = Path(__file__).with_name("content") / "listening_catalog.preview.json"
DEV_CATALOG_FLAG = "ENABLE_DEV_LISTENING_CATALOG"


def dev_catalog_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Whether the generated development overlay may load.

    LISTENING_PRODUCT_SPEC 7: production defaults OFF and publication rules must
    not be weakened. So the flag is opt-in only, and in production it is refused
    outright rather than merely defaulted off - generated development content
    must not be one environment variable away from a production learner.
    """

    values = os.environ if env is None else env
    if str(values.get("APP_ENV", "")).strip().casefold() == "production":
        return False
    return str(values.get(DEV_CATALOG_FLAG, "")).strip().casefold() in {"1", "true", "yes", "on"}


def preview_catalog_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Whether this deployment may load the preview catalog at all.

    Deliberately NOT tied to APP_ENV. A preview deployment runs
    APP_ENV=production so it exercises real security and persistence; what makes
    it a preview is the deployment TIER. Production tier never loads the preview
    artifact, so preview lessons are not merely hidden there - they are absent
    from the process, and no request can reach them.
    """

    return resolve_deployment_tier(env) == TIER_PREVIEW


def _overlay(
    path: Path,
    sources: dict[str, CatalogSource],
    lessons: list[CuratedListeningLesson],
    expected_source_lists: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Merge one generated overlay, returning the lesson ids it contributed.

    Generated content may only ADD. A source or lesson whose id collides with
    something already loaded is dropped, so an overlay can never redefine
    reviewed content.
    """

    tampered = verify_manifest_integrity(
        json.loads(path.read_text(encoding="utf-8")),
        expected_source_lists=expected_source_lists,
    )
    if tampered:
        raise ValueError(f"generated Listening catalog rejected: {tampered}")
    extra_sources, extra_lessons = load_catalog_manifest(path, allow_dev=True)
    for source_id, source in extra_sources.items():
        sources.setdefault(source_id, source)
    known = {lesson.lesson_id for lesson in lessons}
    added = [item for item in extra_lessons if item.lesson_id not in known]
    lessons.extend(added)
    return tuple(item.lesson_id for item in added)


def load_catalog(
    base_path: Path = CATALOG_MANIFEST,
    dev_path: Path = DEV_CATALOG_MANIFEST,
    env: Mapping[str, str] | None = None,
    preview_path: Path = PREVIEW_CATALOG_MANIFEST,
) -> tuple[Mapping[str, CatalogSource], tuple[CuratedListeningLesson, ...]]:
    """BASE VERIFIED CATALOG, plus the DEV GENERATED CATALOG when enabled.

    The base catalog is always loaded and never modified by the overlay; the
    overlay only adds. A dev source or lesson that collides with a base id is
    dropped, so generated content can never redefine reviewed content.
    """

    sources, lessons = load_catalog_manifest(base_path)
    merged_sources = dict(sources)
    merged_lessons = list(lessons)
    preview_ids: tuple[str, ...] = ()

    # Committed artifacts are tamper-evident: a hand edit is refused rather than
    # loaded, which keeps "humans edit only the CSV" true in practice.
    if dev_catalog_enabled(env) and dev_path.is_file():
        _overlay(dev_path, merged_sources, merged_lessons)
    if preview_catalog_enabled(env) and preview_path.is_file():
        # A preview artifact is generated from whatever pilot pack it names, so
        # it is not held to the L3 snapshot's two development CSVs. Every
        # tamper-evidence check still applies.
        preview_ids = _overlay(preview_path, merged_sources, merged_lessons,
                               expected_source_lists=())

    global PREVIEW_LESSON_IDS
    PREVIEW_LESSON_IDS = frozenset(preview_ids)
    return merged_sources, tuple(merged_lessons)


# Lesson ids that came from the preview artifact. Empty on production tier,
# because there the artifact is never loaded at all.
PREVIEW_LESSON_IDS: frozenset[str] = frozenset()
CATALOG_SOURCES, CATALOG = load_catalog()


def _learner_visible(lesson: CuratedListeningLesson) -> bool:
    """Which lessons discovery may offer.

    PUBLISHED is the production answer. A DEV_CANDIDATE is offered only because
    the overlay that carried it was explicitly enabled; it is never relabelled
    PUBLISHED to get there.
    """

    return lesson.content_status in {PUBLIC_CONTENT_STATUS, DEV_CONTENT_STATUS}


def is_preview_lesson(lesson_id: str) -> bool:
    return lesson_id in PREVIEW_LESSON_IDS


def catalog_lesson(
    lesson_id: str,
    *,
    include_preview: bool = False,
) -> CuratedListeningLesson | None:
    """One lesson, refusing preview content unless the caller is authorized.

    The check is here, in the catalog, rather than in a screen: hiding a card in
    JavaScript is not access control, and the lesson endpoint is reachable
    directly.
    """

    if not include_preview and is_preview_lesson(lesson_id):
        return None
    return next(
        (lesson for lesson in CATALOG if lesson.lesson_id == lesson_id and _learner_visible(lesson)),
        None,
    )


def catalog_lessons(
    *, language: str | None = None, level: str | None = None, topic: str | None = None,
    tag: str | None = None, include_preview: bool = False,
) -> tuple[CuratedListeningLesson, ...]:
    language_key = (language or "").strip().casefold()
    level_key = (level or "").strip().casefold()
    topic_key = (topic or "").strip().casefold()
    tag_key = (tag or "").strip().casefold()
    return tuple(
        lesson
        for lesson in CATALOG
        if _learner_visible(lesson)
        and (include_preview or not is_preview_lesson(lesson.lesson_id))
        and (not language_key or lesson.source.language.casefold() == language_key)
        and (not level_key or lesson.level.casefold() == level_key)
        and (
            not topic_key
            or lesson.topic.casefold() == topic_key
            or topic_key in {value.casefold() for value in lesson.subtopics}
        )
        and (not tag_key or tag_key in {value.casefold() for value in lesson.content_tags})
    )


def translated_media_object(lesson: CuratedListeningLesson, target_language: str) -> MediaLearningObject:
    """Project one support language without duplicating canonical segments."""
    target = target_language.strip().casefold()
    translations = tuple(
        item for item in lesson.media_object.translations if item.target_language.casefold() == target
    )
    asset = lesson.media_object.asset
    return MediaLearningObject(
        MediaLearningAsset(
            asset_id=asset.asset_id,
            source_url=asset.source_url,
            source_provider=asset.source_provider,
            source_type=asset.source_type,
            title=asset.title,
            source_language=asset.source_language,
            processing_state=asset.processing_state,
            duration_ms=asset.duration_ms,
            transcript_available=True,
            translation_available=bool(translations),
        ),
        lesson.media_object.transcript,
        translations,
    )


def lesson_metadata(lesson: CuratedListeningLesson) -> dict[str, object]:
    source = lesson.source
    return {
        "lesson_id": lesson.lesson_id,
        "media_object_id": source.source_media_id,
        "title": lesson.media_object.asset.title,
        "description": lesson.description,
        "language": source.language,
        "topic": lesson.topic,
        "subtopics": list(lesson.subtopics),
        "level": lesson.level,
        "estimated_level": lesson.estimated_level,
        "reviewed_level": lesson.reviewed_level,
        "level_source": "editorial-review" if lesson.reviewed_level else "deterministic-estimate",
        "level_evidence": dict(lesson.level_evidence),
        "duration_ms": lesson.duration_ms,
        "excerpt_start_ms": lesson.excerpt_start_ms,
        "excerpt_end_ms": lesson.excerpt_end_ms,
        "available_modes": list(lesson.available_modes),
        "content_tags": list(lesson.content_tags),
        "vocabulary": list(lesson.vocabulary),
        "speech_speed": lesson.speech_speed,
        "artwork": lesson.artwork,
        "poster_url": source.poster_url,
        "playback_kind": source.playback.kind,
        # A curated transcript is persisted at ingestion, so it is READY the
        # moment the lesson loads - and it says what it is.
        "transcript_state": "ready" if source.segments else "unavailable",
        "transcript_origin": source.transcript_origin,
        "transcript_revision": source.transcript_revision,
        "transcript_language": source.transcript_language or source.language,
        "transcript_quality_state": source.transcript_quality_state,
        "transcript_is_generated": source.transcript_is_generated,
        "transcript_is_reviewed": source.transcript_is_reviewed,
        "transcript_provider": source.transcript_provider,
        "transcript_model": source.transcript_model,
        "published_state": lesson.content_status.casefold(),
        "curation_state": lesson.curation_state,
        "is_development_candidate": lesson.content_status == DEV_CONTENT_STATUS,
        "source": {
            "source_media_id": source.source_media_id,
            "provider": source.source_provider,
            "type": source.source_type,
            "title": source.source_title,
            "creator": source.source_creator,
            "source_url": source.source_url,
            "provenance_url": source.provenance_url,
            "license": source.license_name,
            "license_url": source.license_url,
            "allowed_usage_type": source.allowed_usage_type,
            "rights_review_status": source.rights_review_status,
        },
    }
