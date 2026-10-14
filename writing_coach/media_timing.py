"""Optional word-timing enrichment for shared Media Learning content.

This layer is deliberately additive. M1 canonical segment identities and source
text remain authoritative; word timing is interaction metadata consumed by
Listening/Shadowing and may be absent without invalidating the media object.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from typing import Protocol

from writing_coach.media_ingestion import MediaAcquisition
from writing_coach.media_learning import (
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    TranscriptSegment,
)
from writing_coach.speech_asr import (
    SpeechAsrMalformed,
    SpeechAsrPayloadTooLarge,
    SpeechAsrRequestFailed,
    SpeechAsrResult,
    SpeechAsrTimedOut,
)


@dataclass(frozen=True)
class MediaAudioSource:
    """One short-lived provider media URL suitable for remote ASR."""

    url: str
    provider: str
    format_id: str = ""


class MediaAudioUrlResolver(Protocol):
    provider_id: str

    def resolve(self, source_url: str) -> MediaAudioSource: ...


class MediaUrlAsrProvider(Protocol):
    provider_id: str

    @property
    def model(self) -> str: ...

    def transcribe_url(
        self,
        audio_url: str,
        *,
        language: str | None,
    ) -> SpeechAsrResult: ...


@dataclass(frozen=True)
class MediaWordTiming:
    segment_id: str
    text: str
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class MediaTimingEnrichment:
    acquisition: MediaAcquisition
    status: str
    words: tuple[MediaWordTiming, ...] = ()
    source: str | None = None
    model: str | None = None
    failure_kind: str | None = None
    transcript_generated: bool = False


class MediaAudioResolutionFailed(Exception):
    """The provider page did not yield one safe public media-file URL."""


def _primary_language(value: str | None) -> str:
    return str(value or "").split("-", 1)[0].casefold()


def _stable_segment_id(
    asset_id: str,
    start_ms: int,
    end_ms: int,
    text: str,
    occurrence: int,
) -> str:
    fingerprint = hashlib.sha256(
        f"{start_ms}\0{end_ms}\0{text}".encode("utf-8")
    ).hexdigest()
    return f"{asset_id}:segment:{fingerprint}:{occurrence:06d}"


def _transcript_from_asr(
    acquisition: MediaAcquisition,
    result: SpeechAsrResult,
    source_language: str,
) -> MediaAcquisition | None:
    if not result.segments:
        return None

    asset = acquisition.media_object.asset
    seen: dict[str, int] = {}
    segments: list[TranscriptSegment] = []
    for order, segment in enumerate(result.segments):
        text = " ".join(segment.text.split())
        if not text or segment.end_ms <= segment.start_ms:
            continue
        key = f"{segment.start_ms}\0{segment.end_ms}\0{text}"
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        segments.append(
            TranscriptSegment(
                segment_id=_stable_segment_id(
                    asset.asset_id,
                    segment.start_ms,
                    segment.end_ms,
                    text,
                    occurrence,
                ),
                order=len(segments),
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                original_text=text,
            )
        )
    if not segments:
        return None

    transcript = MediaTranscript(
        asset_id=asset.asset_id,
        source_language=source_language,
        segments=tuple(segments),
    )
    media_object = MediaLearningObject(
        asset=replace(
            asset,
            source_language=source_language,
            processing_state=MediaProcessingState.READY,
            transcript_available=True,
            translation_available=False,
        ),
        transcript=transcript,
    )
    return MediaAcquisition(
        media_object=media_object,
        playback=acquisition.playback,
        provenance=acquisition.provenance,
    )


def _segment_for_word(
    word_start: int,
    word_end: int,
    segments: tuple[TranscriptSegment, ...],
) -> TranscriptSegment | None:
    if word_end <= word_start:
        return None
    midpoint = word_start + ((word_end - word_start) / 2)
    for segment in segments:
        if segment.start_ms <= midpoint < segment.end_ms:
            return segment

    best: TranscriptSegment | None = None
    best_overlap = 0
    for segment in segments:
        overlap = min(word_end, segment.end_ms) - max(word_start, segment.start_ms)
        if overlap > best_overlap:
            best = segment
            best_overlap = overlap
    return best if best_overlap > 0 else None


def _map_words(
    result: SpeechAsrResult,
    transcript: MediaTranscript | None,
) -> tuple[MediaWordTiming, ...]:
    if transcript is None:
        return ()
    mapped: list[MediaWordTiming] = []
    for word in result.words:
        text = word.word.strip()
        if not text or word.end_ms <= word.start_ms:
            continue
        segment = _segment_for_word(
            word.start_ms,
            word.end_ms,
            transcript.segments,
        )
        if segment is None:
            continue
        mapped.append(
            MediaWordTiming(
                segment_id=segment.segment_id,
                text=text,
                start_ms=word.start_ms,
                end_ms=word.end_ms,
            )
        )
    return tuple(mapped)


class MediaTimingService:
    """Resolve provider audio and ask the existing Groq ASR boundary for timing."""

    def __init__(
        self,
        resolver: MediaAudioUrlResolver,
        asr_provider: MediaUrlAsrProvider,
    ) -> None:
        self._resolver = resolver
        self._asr_provider = asr_provider

    def enrich(
        self,
        acquisition: MediaAcquisition,
        source_language: str,
    ) -> MediaTimingEnrichment:
        asset = acquisition.media_object.asset
        if asset.source_provider != self._resolver.provider_id:
            return MediaTimingEnrichment(
                acquisition=acquisition,
                status="unavailable",
                failure_kind="unsupported_provider",
            )

        if getattr(self._resolver, "delivery_mode", "url") == "segment_only":
            if acquisition.media_object.transcript is not None:
                return MediaTimingEnrichment(
                    acquisition=acquisition,
                    status="segment_only",
                    failure_kind="word_timing_transport_unavailable",
                )
            return MediaTimingEnrichment(
                acquisition=acquisition,
                status="unavailable",
                failure_kind="word_timing_transport_unavailable",
            )

        try:
            media_source = self._resolver.resolve(asset.source_url)
        except MediaAudioResolutionFailed:
            return MediaTimingEnrichment(
                acquisition=acquisition,
                status="unavailable",
                failure_kind="audio_url_unavailable",
            )

        try:
            result = self._asr_provider.transcribe_url(
                media_source.url,
                language=_primary_language(source_language) or None,
            )
        except SpeechAsrTimedOut:
            failure_kind = "asr_timeout"
        except SpeechAsrMalformed:
            failure_kind = "asr_malformed"
        except SpeechAsrPayloadTooLarge:
            failure_kind = "asr_payload_too_large"
        except SpeechAsrRequestFailed:
            failure_kind = "asr_provider_failure"
        else:
            expected_language = _primary_language(source_language)
            detected_language = _primary_language(result.language)
            if detected_language not in {"", "und", expected_language}:
                return MediaTimingEnrichment(
                    acquisition=acquisition,
                    status="unavailable",
                    source=result.provider,
                    model=result.model,
                    failure_kind="language_mismatch",
                )

            enriched_acquisition = acquisition
            transcript_generated = False
            if acquisition.media_object.transcript is None:
                generated = _transcript_from_asr(
                    acquisition,
                    result,
                    expected_language,
                )
                if generated is not None:
                    enriched_acquisition = generated
                    transcript_generated = True

            words = _map_words(
                result,
                enriched_acquisition.media_object.transcript,
            )
            if words:
                return MediaTimingEnrichment(
                    acquisition=enriched_acquisition,
                    status="ready",
                    words=words,
                    source=result.provider,
                    model=result.model,
                    transcript_generated=transcript_generated,
                )
            if enriched_acquisition.media_object.transcript is not None:
                return MediaTimingEnrichment(
                    acquisition=enriched_acquisition,
                    status="segment_only",
                    source=result.provider,
                    model=result.model,
                    failure_kind="word_timing_unavailable",
                    transcript_generated=transcript_generated,
                )
            failure_kind = "empty_transcript"

        return MediaTimingEnrichment(
            acquisition=acquisition,
            status="unavailable",
            source=getattr(self._asr_provider, "provider_id", None),
            model=getattr(self._asr_provider, "model", None),
            failure_kind=failure_kind,
        )
