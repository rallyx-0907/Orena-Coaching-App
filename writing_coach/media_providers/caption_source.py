"""Where a YouTube item's captions come from (D-215).

`media.caption_source` (policy, env `MEDIA_CAPTION_SOURCE`) is one of

* `youtube` (the default): the public caption client, exactly as before;
* `supadata_native`: Supadata, in its **native** mode only, and YouTube is not asked for captions;
* `youtube_then_supadata_native`: YouTube first; Supadata native only when YouTube gave no track.

Native mode returns the captions the video already has, at one credit a request. `auto` can generate a transcript (two credits
a minute) and translation costs thirty, so neither is ever requested here: the one call below passes `NATIVE_MODE`, a constant.
A day's requests are counted in the media spend ledger (kind `supadata`, one unit, no dollars) and refused past
`media.supadata_daily_requests` with the stable reason `caption_quota` before any call is made. A call is never repeated by this
code; a definitive answer (a track, or none, which includes Supadata's own "no transcript" 206/404/422) is remembered briefly so the import and the pipeline step that follows it do not
pay twice for one video.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from writing_coach import policies
from writing_coach.billing.funding_context import system_funding
from writing_coach.media_ingestion import ProviderRequestFailed, ProviderTimedOut, ProviderUrlMalformed
from writing_coach.media_library_store import valid_provider_media_id
from writing_coach.media_providers.supadata import (
    SupadataTranscriptError,
    SupadataTranscriptMalformed,
    SupadataTranscriptNotFound,
    SupadataTranscriptTimedOut,
)
from writing_coach.media_providers.youtube import (
    YouTubeCaptionClient,
    YouTubeCaptionSnippet,
    YouTubeCaptionTrack,
    canonical_youtube_url,
    TraditionalChineseNotAccepted,
    is_traditional_chinese_tag,
    is_youtube_video_id,
    traditional_chinese_refused,
)
from writing_coach.media_spend import SpendCapReached

_log = logging.getLogger(__name__)

SOURCE_YOUTUBE = "youtube"
SOURCE_SUPADATA_NATIVE = "supadata_native"
SOURCE_YOUTUBE_THEN_SUPADATA_NATIVE = "youtube_then_supadata_native"
CAPTION_SOURCES = (SOURCE_YOUTUBE, SOURCE_SUPADATA_NATIVE, SOURCE_YOUTUBE_THEN_SUPADATA_NATIVE)

PROVIDER = "supadata"
NATIVE_MODE = "native"            # the only mode this module ever sends
KIND_UNKNOWN = "unknown"          # Supadata does not say whether a track is manual or automatic; we do not claim it
REASON_QUOTA = "caption_quota"
REASON_UNCONFIGURED = "caption_unconfigured"

MEMO_SECONDS = 900.0
MEMO_MAX = 64
_MISS = object()


class CaptionQuotaReached(ProviderRequestFailed):
    """Today's Supadata requests reached the cap; nothing was sent."""

    reason = REASON_QUOTA


class CaptionNotConfigured(ProviderRequestFailed):
    """Supadata was chosen as the caption source and this deployment has no key for it."""

    reason = REASON_UNCONFIGURED


def caption_source() -> str:
    return str(policies.value("media.caption_source"))


class PolicyCaptionClient:
    """A `YouTubeCaptionClient` that follows `media.caption_source` each time it is asked (no restart to change it)."""

    def __init__(
        self,
        youtube: YouTubeCaptionClient,
        supadata: Any,
        ledger: Callable[[], Any],
        *,
        source: Callable[[], str] = caption_source,
        daily_cap: Callable[[], int] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._youtube = youtube
        self._supadata = supadata
        self._ledger = ledger
        self._source = source
        self._daily_cap = daily_cap or (lambda: int(policies.value("media.supadata_daily_requests")))
        self._clock = clock
        self._memo: dict[tuple[str, str], tuple[float, YouTubeCaptionTrack | None]] = {}
        self._inflight: dict[tuple[str, str], threading.Lock] = {}
        self._lock = threading.Lock()

    def fetch_track(self, video_id: str, source_language: str) -> YouTubeCaptionTrack | None:
        source = self._source()
        if source not in CAPTION_SOURCES or source == SOURCE_YOUTUBE:
            return self._youtube.fetch_track(video_id, source_language)
        if source == SOURCE_SUPADATA_NATIVE:
            return self._native(video_id, source_language)
        youtube_error: Exception | None = None
        try:
            track = self._youtube.fetch_track(video_id, source_language)
        except TraditionalChineseNotAccepted:
            raise   # the only Chinese track is Traditional: a paid request would not change that (D-218)
        except (ProviderTimedOut, ProviderRequestFailed) as error:
            track, youtube_error = None, error   # a refusal (HTTP 429) is the case this option exists for
        if track is not None:
            return track
        native = self._native(video_id, source_language)
        if native is None and youtube_error is not None:
            raise youtube_error   # neither source had captions, and YouTube refused rather than said "none"
        return native

    def _native(self, video_id: str, source_language: str) -> YouTubeCaptionTrack | None:
        # Every check an id or URL will meet later runs here, before a request is reserved or sent (D-218): the video id's
        # own shape, the item identity the library would store it under, and the URL built from it. An id the store would
        # refuse cost a paid request and then failed the import.
        if not (is_youtube_video_id(video_id) and valid_provider_media_id("youtube", video_id)
                and valid_provider_media_id("youtube", f"youtube-{video_id}")):
            raise ProviderUrlMalformed()
        key = (video_id, source_language.casefold())
        with self._lock:
            flight = self._inflight.setdefault(key, threading.Lock())
        with flight:   # one caller per video and language at a time: the second reads the first's answer from the memo
            kept = self._remembered(key)
            if kept is not _MISS:
                if isinstance(kept, Exception):
                    raise kept   # a remembered rejection is not paid for twice
                return kept
            try:
                return self._ask(key, video_id, source_language)
            finally:
                with self._lock:
                    if len(self._inflight) > 1024:
                        self._inflight = {k: v for k, v in self._inflight.items() if v.locked()}

    def _remembered(self, key: tuple[str, str]) -> Any:
        with self._lock:
            kept = self._memo.get(key)
            if kept is not None and kept[0] > self._clock():
                return kept[1]
            self._memo.pop(key, None)
            return _MISS

    def _remember(self, key: tuple[str, str], track: YouTubeCaptionTrack | Exception | None) -> None:
        with self._lock:
            self._memo.pop(key, None)
            self._memo[key] = (self._clock() + MEMO_SECONDS, track)
            while len(self._memo) > MEMO_MAX:
                self._memo.pop(next(iter(self._memo)))   # the oldest answer goes, not all of them

    def _ask(self, key: tuple[str, str], video_id: str, source_language: str) -> YouTubeCaptionTrack | None:
        client = self._supadata
        if client is None:
            raise CaptionNotConfigured()
        ledger = self._ledger()
        try:
            # Check and record are one step under the ledger's lock, before the call, so a request that dies in flight
            # still counts and two callers cannot both pass the cap.
            ledger.reserve_request(max(0, self._daily_cap()), media_id=f"youtube-{video_id}", provider=PROVIDER)
        except SpendCapReached as refused:
            raise CaptionQuotaReached() from refused
        try:
            with system_funding("media_captions"):
                result = client.fetch(canonical_youtube_url(video_id), source_language, mode=NATIVE_MODE)
        except SupadataTranscriptTimedOut as error:
            raise ProviderTimedOut() from error
        except SupadataTranscriptNotFound:
            track = None   # 206, 404, 422: Supadata has no captions for this video, a definitive answer
        except SupadataTranscriptMalformed:
            # Supadata answered in a language other than the one asked for, or in a shape that is not a transcript: there
            # is no usable track for this language.
            _log.warning("supadata native captions for %s were not usable", video_id)
            track = None
        except SupadataTranscriptError as error:
            raise ProviderRequestFailed() from error
        else:
            track = None
            if (result is not None and result.chunks and source_language.casefold() == "zh"
                    and traditional_chinese_refused() and is_traditional_chinese_tag(result.language)):
                # Only the response reveals the language: the request is already counted, and it is recorded here. The
                # captions are dropped before they become a lesson line, so nothing is translated or spent after it (D-218).
                _log.warning("supadata native captions for %s are tagged %s: Traditional Chinese is not accepted", video_id, result.language)
                refusal = TraditionalChineseNotAccepted()
                self._remember(key, refusal)
                raise refusal
            if result is not None and result.chunks:
                track = YouTubeCaptionTrack(
                    source_language=result.language,
                    snippets=tuple(
                        YouTubeCaptionSnippet(text=chunk.text, start_seconds=chunk.offset_ms / 1000,
                                              duration_seconds=chunk.duration_ms / 1000)
                        for chunk in result.chunks
                    ),
                    kind=KIND_UNKNOWN,
                    provider=PROVIDER,
                )
        self._remember(key, track)
        return track
