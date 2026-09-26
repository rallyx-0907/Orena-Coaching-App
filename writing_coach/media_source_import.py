"""Media-specific source engine: detect → extract → normalize → validate →
thumbnail → persist → publish.

This is deliberately *not* a general ingestion framework. Listening and Speaking
already share one canonical media contract (`media_learning`), one provider
boundary (`media_ingestion` + `media_providers`) and one asset abstraction
(`book_asset_store`); what was missing was the step that turns a source a human
supplied into a persistable library entry with a real thumbnail. That step lives
here, and it is media-specific on purpose — a pipeline shared with Reading or
Vocabulary would be a new abstraction with no second user.

Ownership is a parameter, never a guess: an administrator's import is written
`library="shared"` and every learner may browse it; a learner's own upload is
written `library="personal"` and is only reachable through the unguessable
identity minted for it.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from writing_coach.book_asset_store import BookAssetStore
from writing_coach.media_api import serialize_media_acquisition
from writing_coach.media_ingestion import MediaAcquisition, MediaIngestionService
from writing_coach.media_library_store import MediaLibraryEntry, MediaLibraryStore
from writing_coach.media_safe_fetch import UnsafeMediaFetch, download_bounded, validate_public_http_url
from writing_coach.media_thumbnail import (
    TempMediaFile,
    embedded_audio_artwork,
    probe_media,
    provider_poster_url,
    video_frame_thumbnail,
)

# A URL whose path ends in one of these is treated as a direct media source. The
# extension is only a routing hint - ffprobe decides what the bytes really are,
# so a lying extension costs one failed probe and never a wrong library entry.
DIRECT_MEDIA_SUFFIXES = frozenset(
    {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".mp3", ".m4a", ".wav", ".ogg", ".opus", ".aac", ".flac"}
)

# The human label a card shows for where the media came from. Localisation is
# the interface layer's job; this is provenance, not interface copy.
PROVIDER_LABELS: Mapping[str, str] = {
    "youtube": "YouTube",
    "wikimedia-commons": "Wikimedia Commons",
    "direct": "Direct media URL",
    "upload": "Uploaded file",
}


@dataclass(frozen=True)
class MediaSourceImportItem:
    url: str
    status: str
    detail: str
    media_id: str = ""
    lesson_id: str = ""
    # A stable code the console maps to its own words in its own language.
    # `detail` is the English fallback for anything that reads this API
    # directly; neither is ever the text of a raw exception.
    category: str = ""


@dataclass(frozen=True)
class MediaSourceImportReport:
    items: tuple[MediaSourceImportItem, ...]

    def summary(self) -> dict[str, int]:
        return {
            "ok": sum(item.status == "ok" for item in self.items),
            "error": sum(item.status == "error" for item in self.items),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def public_thumbnail_url(entry: MediaLibraryEntry) -> str:
    """Where the card image lives, as the browser must request it.

    A provider thumbnail stays provider-hosted - Orena does not copy bytes it
    did not have to. A generated thumbnail is Orena's own stored asset and is
    addressed as a same-origin path, which is what the web player's own boundary
    accepts (`capabilities/media-player.js`).
    """
    if entry.thumbnail["kind"] == "provider-url":
        return entry.thumbnail["ref"]
    if entry.thumbnail["kind"] == "asset":
        return f"/api/media/files/{entry.thumbnail['ref']}?variant=thumb"
    return ""


def playback_for(entry: MediaLibraryEntry) -> dict[str, str]:
    """The playback reference in the one shape the player accepts.

    Provider-hosted media keeps the provider's own reference (for YouTube, the
    embed URL) and is never proxied. Media Orena stores itself is served by this
    application, so it names provider `orena` with a same-origin path - the
    player refuses every other absolute host, which is what keeps a stored file
    playable only from the origin that stored it.
    """
    playback = dict(entry.playback)
    if playback.get("provider") in {"upload", "direct"}:
        return {"provider": "orena", "kind": entry.media_type, "url": playback["url"]}
    return playback


def source_label(entry: MediaLibraryEntry) -> str:
    return PROVIDER_LABELS.get(entry.provider, entry.provider)


def _source(provider: str, canonical_url: str, imported_by: str, *, kind: str = "admin-import") -> dict[str, str]:
    """Provenance, stated as exactly what was checked and by whom."""
    return {
        "provider": provider,
        "type": kind,
        "provenance_url": canonical_url,
        "license": (
            "Provider-hosted media; review provider terms before publishing."
            if canonical_url
            else "File supplied to Orena."
        ),
        "review_status": "URL, playback reference and thumbnail checked at import time.",
        "imported_by": imported_by,
    }


def _entry_with(entry: MediaLibraryEntry, **changes: Any) -> MediaLibraryEntry:
    return MediaLibraryEntry(**{**entry.__dict__, **changes})


def _safe_suffix(raw: str) -> str:
    """A suffix safe to put in an asset key, or `.bin` when there is none.

    The asset-key validator accepts `[A-Za-z0-9_.-]` only, so an extension taken
    from a URL or a filename is normalised here rather than allowed to make a
    legitimate import fail.
    """
    suffix = Path(raw).suffix.casefold()
    if suffix.startswith(".") and 1 < len(suffix) <= 8 and suffix[1:].isalnum():
        return suffix
    return ".bin"


def _transcript_duration_ms(acquisition: MediaAcquisition) -> int:
    """Duration from the canonical transcript when the provider reports none.

    YouTube's oEmbed publishes no duration, so the last caption boundary is the
    only true length the acquisition actually has - and an excerpt can never be
    longer than the transcript it was cut from.
    """
    transcript = acquisition.media_object.transcript
    if transcript is None or not transcript.segments:
        return 0
    return max(int(segment.end_ms) for segment in transcript.segments)


def _lesson_projection(lesson_id: str, acquisition: MediaAcquisition, language: str) -> Mapping[str, Any]:
    """The stored lesson *is* the acquisition payload.

    Storing the same serialization the learner API already answers with means
    opening an imported source and opening a curated lesson cannot drift into
    two shapes, and nothing here needs a second transcript model.
    """
    return {
        "lesson_id": lesson_id,
        "payload": serialize_media_acquisition(acquisition),
        "sections": ["new"],
        "status": "PUBLISHED",
        "curation": "reviewed",
        "language": language,
    }


_logger = logging.getLogger(__name__)


class UnsupportedMediaAddress(Exception):
    """A public address that is not a media file this importer can read.

    Its own class rather than a bare `ValueError`, because the sentence that
    goes with it was written for an operator and belongs to a category the
    console can translate. A `ValueError` from anywhere else is an internal
    detail and must not reach them.
    """


class MediaLibraryWriteFailed(Exception):
    """This deployment could not store what was imported.

    Raised only where storage is actually written - the library index and the
    asset store. Everything upstream of that (a provider, a download, a probe,
    a file read) raises its own error for its own reason, and several of them
    are `OSError` too. Keeping the boundary explicit is what stops "the disk is
    read-only" and "the source hung up" from arriving as the same sentence.
    """


def _safe_url_for_log(url: str) -> str:
    """The source, identifiable, without what it was carrying.

    A media URL is operator input and routinely signed: `?token=...`, `?sig=...`,
    sometimes `user:password@`. The log needs to say *which* source failed, and
    the host and path do that. Everything else is dropped rather than
    pattern-matched, because a list of secret-looking parameter names is a list
    that is always one provider out of date.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable url>"
    if not parts.hostname:
        return "<relative url>"
    port = f":{parts.port}" if parts.port else ""
    return f"{parts.scheme}://{parts.hostname}{port}{parts.path}"


def _failure_reason(exc: BaseException) -> tuple[str, str]:
    """(category, sentence) for a failed import.

    Nothing here interpolates `str(exc)` for an exception this code did not
    author. A provider failure already carries a learner-safe sentence; a
    storage failure quotes the operating system's own short description of the
    errno, which is vocabulary rather than detail; everything else gets one
    sentence and leaves its specifics in the log.
    """
    from writing_coach.media_ingestion import MediaImportError

    if isinstance(exc, MediaImportError):
        return exc.category.value, exc.learner_message
    if isinstance(exc, MediaLibraryWriteFailed):
        said = getattr(exc, "reason", "") or "the storage refused the write"
        return (
            "media_library_write_failed",
            f"The media library could not be written: {said}. "
            "This is a deployment problem, not a problem with the source.",
        )
    if isinstance(exc, UnsupportedMediaAddress):
        return "unsupported_media_type", "This address is not a supported media file."
    if isinstance(exc, UnsafeMediaFetch):
        # Authored constants from `media_safe_fetch`, written to be shown.
        return "unsafe_source", str(exc)
    return "import_failed", "This source could not be imported. The server log has the details."


def _write_failure(exc: OSError) -> MediaLibraryWriteFailed:
    failure = MediaLibraryWriteFailed()
    failure.reason = exc.strerror or "the storage refused the write"
    failure.__cause__ = exc
    return failure


class MediaSourceImporter:
    """Detect, acquire, normalise, persist — reusing M1 acquisition throughout."""

    def __init__(self, ingestion: MediaIngestionService, store: MediaLibraryStore, asset_store: BookAssetStore) -> None:
        self._ingestion = ingestion
        self._store = store
        self._asset_store = asset_store

    # -- admin -----------------------------------------------------------------

    def preview(self, url: str, *, language: str) -> dict[str, Any]:
        """Metadata for one source, nothing persisted."""
        entry, acquisition = self._from_url(url, language=language, imported_by="preview", persist_media=False)
        return self._preview_payload(entry, acquisition)

    def import_urls(
        self, items: list[Mapping[str, Any]], *, language: str, imported_by: str
    ) -> MediaSourceImportReport:
        """Import a batch. One bad source is one error row, never a lost batch."""
        results: list[MediaSourceImportItem] = []
        for item in items:
            url = str(item.get("url") or "").strip()
            try:
                entry, _acquisition = self._from_url(
                    url, language=language, imported_by=imported_by, persist_media=True
                )
                entry = self._apply_overrides(entry, item)
            except Exception as exc:  # one bad source must not end the batch
                results.append(self._failed(url, exc))
                continue
            # Persist is its own step so its failures are its own: an OSError
            # here is the library, and an OSError above was something else.
            try:
                self._store.upsert(entry)
            except OSError as exc:
                results.append(self._failed(url, _write_failure(exc)))
                continue
            except Exception as exc:
                results.append(self._failed(url, exc))
                continue
            lesson_id = str((entry.lesson or {}).get("lesson_id") or "")
            results.append(MediaSourceImportItem(url, "ok", "Imported.", entry.media_id, lesson_id, "ok"))
        return MediaSourceImportReport(tuple(results))

    def _failed(self, url: str, exc: BaseException) -> MediaSourceImportItem:
        """Log everything, answer with the category and its sentence."""
        category, detail = _failure_reason(exc)
        _logger.error(
            "media import failed (%s) for %s", category, _safe_url_for_log(url),
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return MediaSourceImportItem(url, "error", detail, category=category)

    def _apply_overrides(self, entry: MediaLibraryEntry, item: Mapping[str, Any]) -> MediaLibraryEntry:
        """Only the fields a human may overrule, and only when they said so.

        Provider-owned facts (title, duration, playback, transcript) come from
        the provider. The administrator owns the editorial metadata a provider
        cannot know - level, topic, tags - and may name an explicit poster only
        for a source whose provider has a reviewed poster host.
        """
        changes: dict[str, Any] = {}
        title = item.get("title")
        if isinstance(title, str) and title.strip():
            changes["title"] = title.strip()[:240]
        level = item.get("level")
        if isinstance(level, str) and level.strip():
            changes["level"] = level.strip().upper()[:16]
        topic = item.get("topic")
        tags = [str(tag).strip()[:32] for tag in (item.get("tags") or []) if str(tag).strip()][:20]
        if entry.lesson is not None and ((isinstance(topic, str) and topic.strip()) or tags):
            lesson = dict(entry.lesson)
            if isinstance(topic, str) and topic.strip():
                lesson["topic"] = topic.strip()[:64]
            if tags:
                lesson["tags"] = tags
            changes["lesson"] = lesson
        requested_poster = item.get("thumbnail_url")
        if isinstance(requested_poster, str) and requested_poster.strip() and entry.provider == "youtube":
            poster = provider_poster_url("youtube", entry.provider_media_id, requested_poster.strip())
            if poster:
                changes["thumbnail"] = {"kind": "provider-url", "ref": poster}
        return _entry_with(entry, **changes) if changes else entry

    def import_upload(
        self,
        path: Path,
        *,
        filename: str,
        language: str,
        imported_by: str,
        library: str = "shared",
        title: str = "",
    ) -> MediaLibraryEntry:
        """Store an audio/video file Orena is given, with its own thumbnail."""
        probe = probe_media(path)
        token = uuid.uuid4().hex
        suffix = _safe_suffix(filename)
        asset_key = f"media/{token}/original{suffix}"
        self._asset_store.put(asset_key, path.read_bytes())
        thumbnail_key = self._persist_thumbnail(path, probe.duration_ms, probe.media_type, token)
        entry = MediaLibraryEntry(
            media_id=f"upload-{token}",
            media_type=probe.media_type,
            provider="upload",
            provider_media_id=token,
            canonical_url="",
            playback={"provider": "orena", "kind": probe.media_type, "url": f"/api/media/files/{asset_key}"},
            title=(title.strip()[:240] or Path(filename).stem[:240] or "Imported media"),
            thumbnail={"kind": "asset", "ref": thumbnail_key} if thumbnail_key else {"kind": "none", "ref": ""},
            duration_ms=probe.duration_ms,
            language=language,
            level="",
            creator="",
            source=_source("upload", "", imported_by, kind="upload"),
            library=library,
            created_at=_now(),
            lesson=None,
        )
        # Both libraries persist through the same store: `personal` rows are
        # simply never listed by a browse read and are only resolvable by id.
        self._store.upsert(entry)
        return entry

    # -- internal --------------------------------------------------------------

    def _from_url(
        self, url: str, *, language: str, imported_by: str, persist_media: bool
    ) -> tuple[MediaLibraryEntry, MediaAcquisition | None]:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        if host in {"youtu.be", "youtube.com"} or host.endswith(".youtube.com"):
            return self._from_youtube(url, language=language, imported_by=imported_by), None
        return self._from_direct_url(url, language=language, imported_by=imported_by, persist_media=persist_media)

    def _from_youtube(self, url: str, *, language: str, imported_by: str) -> MediaLibraryEntry:
        """The provider owns this source; Orena stores the reference, not the video."""
        acquisition = self._ingestion.import_media(url, "en", language)
        asset = acquisition.media_object.asset
        video_id = asset.asset_id.rsplit(":", 1)[-1]
        media_id = f"youtube-{video_id}"
        poster = provider_poster_url("youtube", video_id, asset.thumbnail_ref)
        return MediaLibraryEntry(
            media_id=media_id,
            media_type="video",
            provider="youtube",
            provider_media_id=video_id,
            canonical_url=asset.source_url,
            playback={
                "provider": acquisition.playback.provider,
                "kind": acquisition.playback.kind,
                "url": acquisition.playback.url,
            },
            title=asset.title[:240],
            thumbnail={"kind": "provider-url", "ref": poster} if poster else {"kind": "none", "ref": ""},
            duration_ms=asset.duration_ms or _transcript_duration_ms(acquisition),
            language=language,
            level="",
            creator="",
            source=_source("youtube", asset.source_url, imported_by),
            library="shared",
            created_at=_now(),
            lesson=_lesson_projection(media_id, acquisition, language),
        )

    def _from_direct_url(
        self, url: str, *, language: str, imported_by: str, persist_media: bool
    ) -> tuple[MediaLibraryEntry, MediaAcquisition | None]:
        """A media file on a public host: bounded, SSRF-guarded, probed locally."""
        validate_public_http_url(url)
        suffix = _safe_suffix(urlsplit(url).path)
        if suffix not in DIRECT_MEDIA_SUFFIXES:
            raise UnsupportedMediaAddress
        token = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
        asset_key = f"media/direct-{token}/original{suffix}"
        with TempMediaFile(suffix=suffix) as temp:
            download_bounded(url, temp.path)
            probe = probe_media(temp.path)
            if persist_media:
                # Storage, so a refusal here is the library's and says so.
                try:
                    self._asset_store.put(asset_key, temp.path.read_bytes())
                except OSError as exc:
                    raise _write_failure(exc) from exc
                thumbnail_key = self._persist_thumbnail(
                    temp.path, probe.duration_ms, probe.media_type, f"direct-{token}"
                )
            else:
                thumbnail_key = ""
        return (
            MediaLibraryEntry(
                media_id=f"direct-{token}",
                media_type=probe.media_type,
                provider="direct",
                provider_media_id=token,
                canonical_url=url,
                playback={"provider": "orena", "kind": probe.media_type, "url": f"/api/media/files/{asset_key}"},
                # The filename is not a title, but it is the only true thing
                # known about a direct file before a human edits it.
                title=(Path(urlsplit(url).path).stem[:240] or "Imported media"),
                thumbnail={"kind": "asset", "ref": thumbnail_key} if thumbnail_key else {"kind": "none", "ref": ""},
                duration_ms=probe.duration_ms,
                language=language,
                level="",
                creator="",
                source=_source("direct", url, imported_by),
                library="shared",
                created_at=_now(),
                lesson=None,
            ),
            None,
        )

    def _persist_thumbnail(self, path: Path, duration_ms: int, media_type: str, token: str) -> str:
        """A video gets a real non-blank frame; audio gets its own artwork.

        Neither is invented: when Orena cannot produce either, the entry says so
        and the interface shows the design-system artwork it already has.
        """
        image = (
            video_frame_thumbnail(path, duration_ms=duration_ms)
            if media_type == "video"
            else embedded_audio_artwork(path)
        )
        if not image:
            return ""
        key = f"media/{token}/thumbnail.jpg"
        self._asset_store.put(key, image)
        return key

    @staticmethod
    def _preview_payload(entry: MediaLibraryEntry, acquisition: MediaAcquisition | None) -> dict[str, Any]:
        transcript = acquisition.media_object.transcript if acquisition is not None else None
        return {
            "status": "ok",
            "detail": "Ready to import.",
            "media_id": entry.media_id,
            "media_type": entry.media_type,
            "provider": entry.provider,
            "provider_media_id": entry.provider_media_id,
            "canonical_url": entry.canonical_url,
            "title": entry.title,
            "creator": entry.creator,
            "duration_ms": entry.duration_ms,
            "language": entry.language,
            "level": entry.level,
            "thumbnail_url": public_thumbnail_url(entry),
            "playback": playback_for(entry),
            "has_transcript": entry.lesson is not None or transcript is not None,
            "segment_count": len(transcript.segments) if transcript is not None else 0,
            "poster_allowed": entry.thumbnail["kind"] != "none",
            "source_label": source_label(entry),
        }
