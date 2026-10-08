"""Provider-neutral, learner-neutral contracts for reusable media content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit


class MediaLearningContractError(ValueError):
    """Raised when reusable media content violates the shared contract."""


class MediaProcessingState(str, Enum):
    """Content-processing states independent of any media provider."""

    REGISTERED = "registered"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


_STABLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


def _require_stable_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not _STABLE_ID.fullmatch(value):
        raise MediaLearningContractError(
            f"{field} must be a non-empty stable identifier without whitespace."
        )
    return value


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MediaLearningContractError(f"{field} must be a non-empty string.")
    if value != value.strip():
        raise MediaLearningContractError(f"{field} must not have surrounding whitespace.")
    return value


def _require_language(value: object, field: str) -> str:
    if not isinstance(value, str) or not _LANGUAGE_TAG.fullmatch(value):
        raise MediaLearningContractError(f"{field} must be an explicit language tag.")
    return value


@dataclass(frozen=True)
class MediaLearningAsset:
    """Stable metadata for one reusable imported media source."""

    asset_id: str
    source_url: str
    source_provider: str
    source_type: str
    title: str
    source_language: str
    processing_state: MediaProcessingState
    duration_ms: int | None = None
    transcript_available: bool = False
    translation_available: bool = False
    thumbnail_ref: str = ""

    def __post_init__(self) -> None:
        _require_stable_id(self.asset_id, "asset_id")
        _require_stable_id(self.source_provider, "source_provider")
        _require_stable_id(self.source_type, "source_type")
        _require_text(self.title, "title")
        _require_language(self.source_language, "source_language")

        if not isinstance(self.source_url, str) or self.source_url != self.source_url.strip():
            raise MediaLearningContractError("source_url must be a valid absolute HTTP(S) URL.")
        try:
            parsed_url = urlsplit(self.source_url)
            hostname = parsed_url.hostname
        except ValueError as exc:
            raise MediaLearningContractError(
                "source_url must be a valid absolute HTTP(S) URL."
            ) from exc
        if (
            parsed_url.scheme not in {"http", "https"}
            or not hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise MediaLearningContractError("source_url must be a valid absolute HTTP(S) URL.")

        if not isinstance(self.processing_state, MediaProcessingState):
            raise MediaLearningContractError(
                "processing_state must be a MediaProcessingState value."
            )
        if self.duration_ms is not None and (
            not isinstance(self.duration_ms, int)
            or isinstance(self.duration_ms, bool)
            or self.duration_ms <= 0
        ):
            raise MediaLearningContractError("duration_ms must be a positive integer when known.")
        if not isinstance(self.transcript_available, bool):
            raise MediaLearningContractError("transcript_available must be a boolean.")
        if not isinstance(self.translation_available, bool):
            raise MediaLearningContractError("translation_available must be a boolean.")
        if self.translation_available and not self.transcript_available:
            raise MediaLearningContractError(
                "translation availability requires transcript availability."
            )
        if not isinstance(self.thumbnail_ref, str) or self.thumbnail_ref != self.thumbnail_ref.strip():
            raise MediaLearningContractError("thumbnail_ref must be empty, an HTTPS URL, or an asset key.")
        if self.thumbnail_ref:
            if self.thumbnail_ref.startswith("asset:"):
                _require_stable_id(self.thumbnail_ref.removeprefix("asset:"), "thumbnail_ref")
            else:
                try:
                    thumbnail_url = urlsplit(self.thumbnail_ref)
                except ValueError as exc:
                    raise MediaLearningContractError(
                        "thumbnail_ref must be empty, an HTTPS URL, or an asset key."
                    ) from exc
                if (
                    thumbnail_url.scheme != "https"
                    or not thumbnail_url.hostname
                    or thumbnail_url.username is not None
                    or thumbnail_url.password is not None
                ):
                    raise MediaLearningContractError(
                        "thumbnail_ref must be empty, an HTTPS URL, or an asset key."
                    )


@dataclass(frozen=True)
class TranscriptSegment:
    """One stable, ordered interval of original transcript text."""

    segment_id: str
    order: int
    start_ms: int
    end_ms: int
    original_text: str

    def __post_init__(self) -> None:
        _require_stable_id(self.segment_id, "segment_id")
        if not isinstance(self.order, int) or isinstance(self.order, bool) or self.order < 0:
            raise MediaLearningContractError("segment order must be a non-negative integer.")
        if (
            not isinstance(self.start_ms, int)
            or isinstance(self.start_ms, bool)
            or self.start_ms < 0
        ):
            raise MediaLearningContractError("segment start_ms must be a non-negative integer.")
        if (
            not isinstance(self.end_ms, int)
            or isinstance(self.end_ms, bool)
            or self.end_ms <= self.start_ms
        ):
            raise MediaLearningContractError("segment end_ms must be greater than start_ms.")
        _require_text(self.original_text, "segment original_text")


@dataclass(frozen=True)
class MediaTranscript:
    """The canonical source-language transcript shared by learning consumers."""

    asset_id: str
    source_language: str
    segments: tuple[TranscriptSegment, ...]

    def __post_init__(self) -> None:
        _require_stable_id(self.asset_id, "asset_id")
        _require_language(self.source_language, "source_language")
        if not isinstance(self.segments, tuple) or not self.segments:
            raise MediaLearningContractError("segments must be a non-empty tuple.")
        if not all(isinstance(segment, TranscriptSegment) for segment in self.segments):
            raise MediaLearningContractError("segments must contain TranscriptSegment values.")

        segment_ids = [segment.segment_id for segment in self.segments]
        segment_orders = [segment.order for segment in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise MediaLearningContractError("transcript segment identities must be unique.")
        if len(segment_orders) != len(set(segment_orders)):
            raise MediaLearningContractError("transcript segment orders must be unique.")
        if segment_orders != sorted(segment_orders):
            raise MediaLearningContractError(
                "transcript segments must be supplied in deterministic order."
            )
        starts = [segment.start_ms for segment in self.segments]
        if starts != sorted(starts):
            raise MediaLearningContractError(
                "transcript segment timestamps must follow segment order."
            )


@dataclass(frozen=True)
class SegmentTranslation:
    """A support-language meaning mapped to one canonical transcript segment."""

    segment_id: str
    target_language: str
    translated_meaning: str

    def __post_init__(self) -> None:
        _require_stable_id(self.segment_id, "segment_id")
        _require_language(self.target_language, "target_language")
        _require_text(self.translated_meaning, "translated_meaning")


@dataclass(frozen=True)
class MediaLearningObject:
    """Reusable media content, deliberately excluding learner-specific state."""

    asset: MediaLearningAsset
    transcript: MediaTranscript | None = None
    translations: tuple[SegmentTranslation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.asset, MediaLearningAsset):
            raise MediaLearningContractError("asset must be a MediaLearningAsset.")
        if self.transcript is not None and not isinstance(self.transcript, MediaTranscript):
            raise MediaLearningContractError("transcript must be a MediaTranscript when present.")
        if not isinstance(self.translations, tuple) or not all(
            isinstance(translation, SegmentTranslation) for translation in self.translations
        ):
            raise MediaLearningContractError(
                "translations must be a tuple of SegmentTranslation values."
            )

        has_transcript = self.transcript is not None
        if self.asset.transcript_available != has_transcript:
            raise MediaLearningContractError(
                "asset transcript availability must match the reusable transcript content."
            )
        if self.asset.translation_available != bool(self.translations):
            raise MediaLearningContractError(
                "asset translation availability must match the reusable translation content."
            )
        if self.transcript is None:
            if self.translations:
                raise MediaLearningContractError("translations require a reusable transcript.")
            return

        if self.transcript.asset_id != self.asset.asset_id:
            raise MediaLearningContractError("transcript asset_id must match its media asset.")
        if self.transcript.source_language.casefold() != self.asset.source_language.casefold():
            raise MediaLearningContractError(
                "transcript source_language must match its media asset."
            )
        if self.asset.duration_ms is not None and any(
            segment.end_ms > self.asset.duration_ms for segment in self.transcript.segments
        ):
            raise MediaLearningContractError("transcript segment exceeds the media duration.")

        segment_ids = {segment.segment_id for segment in self.transcript.segments}
        translation_keys: set[tuple[str, str]] = set()
        for translation in self.translations:
            if translation.segment_id not in segment_ids:
                raise MediaLearningContractError(
                    "translation must map to an existing transcript segment."
                )
            key = (translation.segment_id, translation.target_language.casefold())
            if key in translation_keys:
                raise MediaLearningContractError(
                    "each segment and target language may have only one translation."
                )
            translation_keys.add(key)
