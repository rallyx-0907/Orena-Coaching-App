"""YouTube public-caption adapter for the shared Media Learning boundary."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import parse_qs, urlsplit

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    InvalidVideoId,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeTranscriptApiException,
)

from writing_coach.media_providers.supadata import (
    SupadataTranscriptClient,
    SupadataTranscriptMalformed,
    SupadataTranscriptRequestFailed,
    SupadataTranscriptTimedOut,
)
from writing_coach.media_ingestion import (
    MediaAcquisition,
    MediaPlayback,
    ProviderRequestFailed,
    ProviderSourceUnavailable,
    ProviderTimedOut,
    ProviderTranscriptMalformed,
    ProviderUrlMalformed,
    primary_language,
)
from writing_coach.media_transcript_quality import CaptionUnit, clean_caption_units
from writing_coach.media_learning import (
    MediaLearningAsset,
    MediaLearningContractError,
    MediaLearningObject,
    MediaProcessingState,
    MediaTranscript,
    TranscriptSegment,
)


YOUTUBE_PROVIDER_ID = "youtube"
_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_OEMBED_ENDPOINT = "https://www.youtube.com/oembed"


# Why an acquisition carries the transcript it does.
TRANSCRIPT_NATIVE = "native"
TRANSCRIPT_GENERATED = "generated"
TRANSCRIPT_ABSENT = "absent"
TRANSCRIPT_MALFORMED = "malformed"
TRANSCRIPT_PROBE_FAILED = "probe_failed"


@dataclass(frozen=True)
class YouTubeCaptionSnippet:
    """Provider caption fields before deterministic M1.1 normalization."""

    text: object
    start_seconds: object
    duration_seconds: object


@dataclass(frozen=True)
class YouTubeCaptionTrack:
    """One provider transcript track and its explicit source language."""

    source_language: object
    snippets: tuple[YouTubeCaptionSnippet, ...]


class YouTubeMetadataClient(Protocol):
    def fetch_title(self, canonical_source_url: str) -> str: ...


@dataclass(frozen=True)
class YouTubeSourceMetadata:
    """What oEmbed already tells us about a source, beyond its title.

    The channel is the authoritative creator for provenance; an editor's CSV
    `source_family` is a hint, not the source's identity.
    """

    title: str
    author_name: str = ""
    thumbnail_url: str = ""


class YouTubeCaptionClient(Protocol):
    def fetch_track(
        self,
        video_id: str,
        source_language: str,
    ) -> YouTubeCaptionTrack | None: ...


class BoundedYouTubeSession(requests.Session):
    """Apply a provider timeout to every request made by the caption dependency."""

    def __init__(self, timeout_seconds: float = 10) -> None:
        super().__init__()
        self._timeout_seconds = timeout_seconds

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self._timeout_seconds)
        return super().request(method, url, **kwargs)


class RequestsYouTubeMetadataClient:
    """Bounded access to YouTube's public oEmbed metadata representation."""

    def __init__(self, session: requests.Session | None = None, timeout_seconds: float = 10) -> None:
        self._session = session or requests.Session()
        self._timeout_seconds = timeout_seconds
        self._cached_url: str | None = None
        self._cached: YouTubeSourceMetadata | None = None

    def fetch_title(self, canonical_source_url: str) -> str:
        return self.fetch_metadata(canonical_source_url).title

    def fetch_metadata(self, canonical_source_url: str) -> YouTubeSourceMetadata:
        """Title, channel and thumbnail from ONE oEmbed representation.

        acquire() needs the title and the importer needs the channel and the
        thumbnail, and all three arrive in the same payload. Without the memo
        below each candidate cost two identical oEmbed requests, which matters
        at the scale the development source pack is heading for.

        The memo is keyed by canonical URL and holds one entry: consecutive
        lookups for the same source reuse the response, and moving on to the
        next source releases it rather than accumulating a session-long cache.
        """

        if self._cached_url == canonical_source_url and self._cached is not None:
            return self._cached

        try:
            response = self._session.get(
                _OEMBED_ENDPOINT,
                params={"url": canonical_source_url, "format": "json"},
                timeout=self._timeout_seconds,
            )
            if response.status_code in {400, 401, 403, 404}:
                raise ProviderSourceUnavailable()
            response.raise_for_status()
            payload = response.json()
        except ProviderSourceUnavailable:
            raise
        except requests.Timeout as exc:
            raise ProviderTimedOut() from exc
        except (requests.RequestException, ValueError) as exc:
            raise ProviderRequestFailed() from exc

        if not isinstance(payload, dict):
            raise ProviderRequestFailed()
        title = " ".join(str(payload.get("title") or "").split())
        if not title:
            raise ProviderRequestFailed()
        metadata = YouTubeSourceMetadata(
            title=title,
            author_name=" ".join(str(payload.get("author_name") or "").split()),
            thumbnail_url=str(payload.get("thumbnail_url") or "").strip(),
        )
        self._cached_url, self._cached = canonical_source_url, metadata
        return metadata


class PublicYouTubeCaptionClient:
    """Caption-only wrapper around the small public transcript dependency."""

    def __init__(
        self,
        api: YouTubeTranscriptApi | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        self._api = api or YouTubeTranscriptApi(
            http_client=BoundedYouTubeSession(timeout_seconds)
        )

    def fetch_track(
        self,
        video_id: str,
        source_language: str,
    ) -> YouTubeCaptionTrack | None:
        try:
            transcript_list = self._api.list(video_id)
            language_candidates = sorted(
                {
                    language_code
                    for transcript in transcript_list
                    if isinstance(
                        language_code := getattr(transcript, "language_code", None),
                        str,
                    )
                    and primary_language(language_code) == source_language.casefold()
                },
                key=lambda code: (
                    code.casefold() != source_language.casefold(),
                    code.casefold(),
                ),
            )
            if not language_candidates:
                return None
            try:
                selected = transcript_list.find_manually_created_transcript(
                    language_candidates
                )
            except NoTranscriptFound:
                try:
                    selected = transcript_list.find_generated_transcript(
                        language_candidates
                    )
                except NoTranscriptFound:
                    return None
            fetched = selected.fetch()
            fetched_language = getattr(fetched, "language_code", None)
            if (
                not isinstance(fetched_language, str)
                or primary_language(fetched_language) != source_language.casefold()
            ):
                raise ProviderTranscriptMalformed()
            fetched_snippets = tuple(fetched)
            if not fetched_snippets:
                return None
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except (VideoUnavailable, VideoUnplayable, AgeRestricted, InvalidVideoId) as exc:
            raise ProviderSourceUnavailable() from exc
        except requests.Timeout as exc:
            raise ProviderTimedOut() from exc
        except requests.RequestException as exc:
            raise ProviderRequestFailed() from exc
        except (CouldNotRetrieveTranscript, YouTubeTranscriptApiException) as exc:
            raise ProviderRequestFailed() from exc

        snippets = tuple(
            YouTubeCaptionSnippet(
                text=getattr(snippet, "text", None),
                start_seconds=getattr(snippet, "start", None),
                duration_seconds=getattr(snippet, "duration", None),
            )
            for snippet in fetched_snippets
        )
        return YouTubeCaptionTrack(
            source_language=fetched_language,
            snippets=snippets,
        )


def recognizes_youtube_url(source_url: str) -> bool:
    """Return whether the parsed hostname belongs to the YouTube adapter."""
    try:
        hostname = (urlsplit(source_url).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    return hostname == "youtu.be" or hostname == "youtube.com" or hostname.endswith(
        ".youtube.com"
    )


def parse_youtube_video_id(source_url: str) -> str:
    """Extract and validate one public YouTube video identity."""
    try:
        parsed = urlsplit(source_url)
        hostname = (parsed.hostname or "").casefold().rstrip(".")
    except ValueError as exc:
        raise ProviderUrlMalformed() from exc

    video_id = ""
    if hostname == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif hostname == "youtube.com" or hostname.endswith(".youtube.com"):
        path_parts = [part for part in parsed.path.split("/") if part]
        if parsed.path.rstrip("/") == "/watch":
            video_id = (parse_qs(parsed.query).get("v") or [""])[0]
        elif len(path_parts) == 2 and path_parts[0].casefold() == "shorts":
            video_id = path_parts[1]

    if not _VIDEO_ID.fullmatch(video_id):
        raise ProviderUrlMalformed()
    return video_id


def canonical_youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def youtube_embed_url(video_id: str) -> str:
    return f"https://www.youtube-nocookie.com/embed/{video_id}"


def normalize_youtube_transcript(
    asset_id: str,
    track: YouTubeCaptionTrack,
) -> MediaTranscript:
    """Purely normalize provider caption data into the M1.1 transcript contract."""
    if not isinstance(track.source_language, str) or not track.source_language.strip():
        raise ProviderTranscriptMalformed()
    if track.source_language != track.source_language.strip() or not track.snippets:
        raise ProviderTranscriptMalformed()

    cleaned_snippets = clean_caption_units(
        tuple(
            CaptionUnit(
                text=str(snippet.text or ""),
                start_seconds=snippet.start_seconds,
                duration_seconds=snippet.duration_seconds,
                provider_order=provider_order,
            )
            for provider_order, snippet in enumerate(track.snippets)
        ),
        source_language=track.source_language,
    )
    if not cleaned_snippets:
        raise ProviderTranscriptMalformed()

    normalized: list[tuple[int, int, int, str]] = []
    for provider_order, snippet in enumerate(cleaned_snippets):
        start = _finite_number(snippet.start_seconds)
        duration = _finite_number(snippet.duration_seconds)
        text = snippet.text
        if start < 0 or duration <= 0 or not text:
            raise ProviderTranscriptMalformed()
        start_ms = round(start * 1000)
        duration_ms = max(1, round(duration * 1000))
        normalized.append((start_ms, start_ms + duration_ms, provider_order, text))

    normalized.sort(key=lambda item: (item[0], item[1], item[2]))
    fingerprint_occurrences: dict[str, int] = {}
    segments_list: list[TranscriptSegment] = []
    for order, (start_ms, end_ms, _provider_order, text) in enumerate(normalized):
        fingerprint = hashlib.sha256(
            f"{start_ms}\0{end_ms}\0{text}".encode("utf-8")
        ).hexdigest()
        occurrence = fingerprint_occurrences.get(fingerprint, 0)
        fingerprint_occurrences[fingerprint] = occurrence + 1
        segments_list.append(
            TranscriptSegment(
                segment_id=f"{asset_id}:segment:{fingerprint}:{occurrence:06d}",
                order=order,
                start_ms=start_ms,
                end_ms=end_ms,
                original_text=text,
            )
        )
    segments = tuple(segments_list)
    try:
        return MediaTranscript(
            asset_id=asset_id,
            source_language=track.source_language,
            segments=segments,
        )
    except MediaLearningContractError as exc:
        raise ProviderTranscriptMalformed() from exc


def _finite_number(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ProviderTranscriptMalformed()
    number = float(value)
    if not math.isfinite(number):
        raise ProviderTranscriptMalformed()
    return number


class YouTubeMediaProviderAdapter:
    """Acquire metadata and public captions without downloading provider media."""

    provider_id = YOUTUBE_PROVIDER_ID

    def __init__(
        self,
        metadata_client: YouTubeMetadataClient | None = None,
        caption_client: YouTubeCaptionClient | None = None,
        fallback_transcript_client: SupadataTranscriptClient | None = None,
        *,
        enable_fallback: bool = True,
        defer_transcript_recovery: bool = False,
    ) -> None:
        self._metadata_client = metadata_client or RequestsYouTubeMetadataClient()
        self._caption_client = caption_client or PublicYouTubeCaptionClient()
        self._fallback_transcript_client = (
            (
                fallback_transcript_client
                if fallback_transcript_client is not None
                else SupadataTranscriptClient.from_env()
            )
            if enable_fallback
            else None
        )
        self._defer_transcript_recovery = bool(defer_transcript_recovery)

    def _fallback_track(
        self,
        canonical_source_url: str,
        source_language: str,
        *,
        mode: str,
    ) -> YouTubeCaptionTrack | None:
        client = self._fallback_transcript_client
        if client is None:
            return None
        try:
            result = client.fetch(
                canonical_source_url,
                source_language,
                mode=mode,
            )
        except SupadataTranscriptTimedOut as exc:
            raise ProviderTimedOut() from exc
        except SupadataTranscriptMalformed as exc:
            raise ProviderTranscriptMalformed() from exc
        except SupadataTranscriptRequestFailed as exc:
            raise ProviderRequestFailed() from exc

        if result is None:
            return None
        snippets = tuple(
            YouTubeCaptionSnippet(
                text=chunk.text,
                start_seconds=chunk.offset_ms / 1000,
                duration_seconds=chunk.duration_ms / 1000,
            )
            for chunk in result.chunks
        )
        if not snippets:
            return None
        return YouTubeCaptionTrack(
            source_language=result.language,
            snippets=snippets,
        )

    def recognizes(self, source_url: str) -> bool:
        return recognizes_youtube_url(source_url)

    def acquire(
        self,
        source_url: str,
        source_language: str,
    ) -> MediaAcquisition:
        video_id = parse_youtube_video_id(source_url)
        canonical_url = canonical_youtube_url(video_id)
        title = self._metadata_client.fetch_title(canonical_url)
        native_caption_error: ProviderTimedOut | ProviderRequestFailed | None = None
        try:
            track = self._caption_client.fetch_track(video_id, source_language)
        except (ProviderTimedOut, ProviderRequestFailed) as exc:
            track = None
            native_caption_error = exc
        asset_id = f"youtube:{video_id}"

        transcript = None
        native_malformed = False
        from_fallback = False
        if track is not None:
            try:
                transcript = normalize_youtube_transcript(asset_id, track)
            except ProviderTranscriptMalformed:
                native_malformed = True

        if transcript is None:
            fallback_track = self._fallback_track(
                canonical_url,
                source_language,
                mode="generate" if native_malformed else "auto",
            )
            if fallback_track is not None:
                transcript = normalize_youtube_transcript(asset_id, fallback_track)
                from_fallback = transcript is not None

        if transcript is None and not self._defer_transcript_recovery:
            if native_malformed:
                raise ProviderTranscriptMalformed()
            if native_caption_error is not None:
                raise native_caption_error

        # Deferral means a missing transcript is not fatal. It must NOT mean a
        # failed caption request is quietly reported as "this source has no
        # captions": one is a fact about the source, the other is a fact about
        # the network, and only the first should ever be acted on.
        if transcript is not None:
            # A transcript the recovery chain generated is NOT the source's own
            # captions. Labelling it "native" would let generated ASR be
            # presented to a learner as official captions.
            transcript_status = TRANSCRIPT_GENERATED if from_fallback else TRANSCRIPT_NATIVE
        elif native_malformed:
            transcript_status = TRANSCRIPT_MALFORMED
        elif native_caption_error is not None:
            transcript_status = TRANSCRIPT_PROBE_FAILED
        else:
            transcript_status = TRANSCRIPT_ABSENT
        source_language = transcript.source_language if transcript is not None else "und"
        asset = MediaLearningAsset(
            asset_id=asset_id,
            source_url=canonical_url,
            source_provider=self.provider_id,
            source_type="external-video",
            title=title,
            source_language=source_language,
            processing_state=MediaProcessingState.READY,
            duration_ms=None,
            transcript_available=transcript is not None,
            translation_available=False,
        )
        try:
            media_object = MediaLearningObject(asset=asset, transcript=transcript)
        except MediaLearningContractError as exc:
            raise ProviderTranscriptMalformed() from exc
        return MediaAcquisition(
            media_object=media_object,
            playback=MediaPlayback(
                provider=self.provider_id,
                kind="embed",
                url=youtube_embed_url(video_id),
            ),
            transcript_status=transcript_status,
        )
