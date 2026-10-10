"""Media becomes a lesson only when it has a usable transcript (D-110, D-111).

    source / import  ->  transcript  ->  lesson lines  ->  validation  ->  rights  ->  publish | review

Every media item the library takes in - an operator's URL or file, a learner's
own upload or link - enters as `processing` and stays out of every learner list
until this pipeline has given it a transcript that passes the deterministic
checks in `media_segmentation`. Where the transcript comes from, in order:

1. the provider's own captions, when it has them and they pass the checks;
2. speech recognition on the audio (the one `speech_asr` boundary), when there
   are no captions or they are not good enough. A stored file is read from the
   asset store; a YouTube source's audio is fetched for this step only and is
   not kept.

The transcript is then cut into lesson lines (`segment_lines`), checked, built
into the one stored-lesson payload the Listening room already reads, given
meaning in the configured support languages through the same cached translation
cache that learner reads consume without a provider, and decided:

* a learner's own import is theirs alone, so it simply becomes usable;
* a shared item publishes by itself only when its rights are cleared for
  automation AND every check passed (D-111 item 1 - no model confidence is
  consulted); anything else is held for review with a stable reason code.

Paid steps (speech recognition, translation) go through the spend ledger
(`media_spend`) and refuse to start past a cap. Nothing in a request waits for
any of this: jobs run on a small thread pool inside the application process
(the media index is a single-process file store), their state lives on the
entry itself, and a restart re-queues what was in flight.
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from writing_coach import media_quota
from writing_coach.ai.audio_telemetry import telemetry_origin
from writing_coach.ai.pricing import estimate_token_cost
from writing_coach.book_asset_store import AssetNotFound, BookAssetStore
from writing_coach.media_learning import MediaTranscript, TranscriptSegment
from writing_coach.media_library_store import MediaLibraryEntry
from writing_coach.media_segmentation import Cue, first_failure, primary_language, segment_lines, validate_lines
from writing_coach.media_spend import KIND_AI, KIND_ASR, SpendCapReached, SpendLedger
from writing_coach.speech_asr import (
    SpeechAsrMalformed,
    SpeechAsrPayloadTooLarge,
    SpeechAsrRequestFailed,
    SpeechAsrResult,
    SpeechAsrTimedOut,
    SpeechAsrWord,
)

_logger = logging.getLogger(__name__)

# The stages, in the order the operator's steps and the learner's sheet show them.
STAGE_FETCH = "fetch"
STAGE_TRANSCRIBE = "transcribe"
STAGE_SEGMENT = "segment"
STAGE_TRANSLATE = "translate"
STAGE_READY = "ready"
STAGES = (STAGE_FETCH, STAGE_TRANSCRIBE, STAGE_SEGMENT, STAGE_TRANSLATE, STAGE_READY)

STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_READY = "ready"
STATE_HELD = "held"      # transcript is fine, a person has to decide (rights unknown)
STATE_FAILED = "failed"  # no usable transcript; retryable

ORIGIN_CAPTION = "provider_caption"
ORIGIN_ASR = "generated_asr"

CHUNK_SECONDS = 600
MAX_ATTEMPTS = 3
AUDIO_FORMAT_TIMEOUT = 600


class PipelineStop(Exception):
    """A stage cannot continue. `code` is the stable reason an operator sees."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _env_int(name: str, default: int) -> int:
    try:
        value = int(str(os.getenv(name, "")).strip())
    except ValueError:
        return default
    return value if value > 0 else default


def max_asr_seconds() -> int:
    """The longest source speech recognition will take (`MEDIA_ASR_MAX_SECONDS`, 90 minutes): also the most one
    import can be charged (`media_quota`)."""
    return _env_int("MEDIA_ASR_MAX_SECONDS", 5400)


# -- rights ---------------------------------------------------------------------------------

RIGHTS_CLEARED = "cleared"
RIGHTS_UNKNOWN = "unknown"


def rights_for_source(provider: str, canonical_url: str, *, declared: bool | None, env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """(rights, basis) for a new shared item, decided at the source, never by a model.

    `declared` is an operator's explicit statement for this import (the API's
    `rights_cleared`); otherwise the deployment's source policy applies:
    `MEDIA_RIGHTS_CLEARED_PROVIDERS` and `MEDIA_RIGHTS_CLEARED_HOSTS`, both
    comma lists and both empty by default - unknown rights is not published
    (D-111 item 2).
    """
    values = os.environ if env is None else env
    if declared is True:
        return RIGHTS_CLEARED, "operator-declared"
    if declared is False:
        return RIGHTS_UNKNOWN, "operator-declared-not-cleared"
    providers = {item.strip().casefold() for item in str(values.get("MEDIA_RIGHTS_CLEARED_PROVIDERS", "")).split(",") if item.strip()}
    if provider.casefold() in providers:
        return RIGHTS_CLEARED, f"source-policy:{provider.casefold()}"
    hosts = {item.strip().casefold() for item in str(values.get("MEDIA_RIGHTS_CLEARED_HOSTS", "")).split(",") if item.strip()}
    if canonical_url and hosts:
        from urllib.parse import urlsplit

        host = (urlsplit(canonical_url).hostname or "").casefold()
        if host in hosts or any(host.endswith("." + item) for item in hosts):
            return RIGHTS_CLEARED, f"source-policy:{host}"
    return RIGHTS_UNKNOWN, "no-source-policy"


# -- audio ----------------------------------------------------------------------------------


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(args, capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _probe_seconds(path: Path) -> float:
    result = _run(["ffprobe", "-protocol_whitelist", "file,pipe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], 60)
    if result is None or result.returncode != 0:
        return 0.0
    try:
        value = float(result.stdout.decode().strip().splitlines()[0])
    except (ValueError, IndexError):
        return 0.0
    return value if math.isfinite(value) and value > 0 else 0.0


def audio_chunks(source: Path, work: Path, chunk_seconds: int = CHUNK_SECONDS) -> list[tuple[Path, float]]:
    """Mono 16 kHz speech-sized mp3 chunks of any audio or video file, with each one's start offset in seconds."""
    pattern = work / "chunk-%03d.mp3"
    result = _run(
        [
            "ffmpeg", "-protocol_whitelist", "file,pipe", "-nostdin", "-v", "error", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "libmp3lame", "-b:a", "48k", "-f", "segment", "-segment_time", str(chunk_seconds),
            "-reset_timestamps", "1", str(pattern),
        ],
        AUDIO_FORMAT_TIMEOUT,
    )
    if result is None or result.returncode != 0:
        raise PipelineStop("audio_unavailable")
    chunks: list[tuple[Path, float]] = []
    offset = 0.0
    for path in sorted(work.glob("chunk-*.mp3")):
        length = _probe_seconds(path)
        if length <= 0:
            continue
        chunks.append((path, offset))
        offset += length
    if not chunks:
        raise PipelineStop("audio_unavailable")
    return chunks


# -- the pipeline ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """What an importer already holds for the first attempt, so it is not fetched twice."""

    cues: tuple[Cue, ...] = ()
    detected_language: str = ""


def _asr_cues(results: list[tuple[SpeechAsrResult, float]]) -> tuple[list[Cue], list[SpeechAsrWord], str]:
    cues: list[Cue] = []
    words: list[SpeechAsrWord] = []
    detected = ""
    for result, offset in results:
        shift = round(offset * 1000)
        detected = detected or result.language
        segments = result.segments
        for segment in segments:
            cues.append(Cue(segment.start_ms + shift, segment.end_ms + shift, segment.text))
        if not segments and result.text.strip():
            # A provider that returned text without segments: one cue spanning the chunk's words, if it has them.
            if result.words:
                cues.append(Cue(result.words[0].start_ms + shift, result.words[-1].end_ms + shift, result.text))
        for word in result.words:
            words.append(SpeechAsrWord(word.word, word.start_ms + shift, word.end_ms + shift))
    return cues, words, detected


def _stable_segment_id(asset_id: str, start_ms: int, end_ms: int, text: str, occurrence: int) -> str:
    fingerprint = hashlib.sha256(f"{start_ms}\0{end_ms}\0{text}".encode()).hexdigest()
    return f"{asset_id}:segment:{fingerprint}:{occurrence:06d}"


def build_transcript(asset_id: str, language: str, lines: list[Cue]) -> MediaTranscript:
    seen: dict[str, int] = {}
    segments: list[TranscriptSegment] = []
    for line in lines:
        key = f"{line.start_ms}\0{line.end_ms}\0{line.text}"
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1
        segments.append(
            TranscriptSegment(
                segment_id=_stable_segment_id(asset_id, line.start_ms, line.end_ms, line.text, occurrence),
                order=len(segments),
                start_ms=line.start_ms,
                end_ms=line.end_ms,
                original_text=line.text,
            )
        )
    return MediaTranscript(asset_id=asset_id, source_language=language, segments=tuple(segments))


def lines_from_payload(payload: Mapping[str, Any] | None) -> list[Cue]:
    transcript = (payload or {}).get("transcript") if isinstance(payload, Mapping) else None
    rows = (transcript or {}).get("segments") if isinstance(transcript, Mapping) else None
    lines: list[Cue] = []
    for row in rows or []:
        try:
            lines.append(Cue(int(row["start_ms"]), int(row["end_ms"]), str(row["original_text"])))
        except (KeyError, TypeError, ValueError):
            return []
    return lines


def usable_transcript(entry: MediaLibraryEntry) -> tuple[bool, str]:
    """Whether a stored entry's transcript passes every deterministic check, and the first reason it does not.

    The one definition used before anything is published, by the pipeline or by an operator's
    Publish: a person may decide rights, never override a transcript that is not usable.
    """
    payload = (entry.lesson or {}).get("payload") if entry.lesson else None
    lines = lines_from_payload(payload)
    if not lines:
        return False, "empty_transcript"
    checks = validate_lines(lines, language=entry.language, duration_ms=int(entry.duration_ms or 0))
    reason = first_failure(checks)
    return (not reason), reason


class MediaPipeline:
    def __init__(
        self,
        *,
        ledger: SpendLedger,
        asr: Any = None,
        ingestion: Any = None,
        youtube_audio: Callable[..., Path] | None = None,
        meanings: Callable[[MediaLibraryEntry, str], Any] | None = None,
        english_reading: Callable[[str], str] | None = None,
        workers: int | None = None,
        translation_sink: Callable[[Callable[[str, Any], None]], Any] | None = None,
    ) -> None:
        self._ledger = ledger
        self._asr = asr
        self._ingestion = ingestion
        self._youtube_audio = youtube_audio
        self._meanings = meanings
        self._english_reading = english_reading
        self._translation_sink = translation_sink
        self._pool = ThreadPoolExecutor(max_workers=workers or _env_int("MEDIA_PIPELINE_WORKERS", 2), thread_name_prefix="media-pipeline")
        self._inflight: set[str] = set()
        self._guard = threading.Lock()

    @property
    def ledger(self) -> SpendLedger:
        return self._ledger

    # -- scheduling ---------------------------------------------------------------------

    @staticmethod
    def new_batch() -> str:
        return f"batch-{uuid.uuid4().hex[:12]}"

    def enqueue(self, store: Any, assets: BookAssetStore, media_id: str, *, batch_id: str, candidate: Candidate | None = None) -> None:
        """Mark the item queued and run it off the request thread (or inline when `MEDIA_PIPELINE_INLINE` is set)."""
        entry = store.get(media_id)
        if entry is None:
            return
        self._write_processing(store, entry, state=STATE_QUEUED, stage=STAGE_FETCH, reason="", detail="", batch_id=batch_id, status="processing")
        with self._guard:
            if media_id in self._inflight:
                return
            self._inflight.add(media_id)
        if os.getenv("MEDIA_PIPELINE_INLINE", "").strip() in {"1", "true", "yes"}:
            self._job(store, assets, media_id, batch_id, candidate)
        else:
            self._pool.submit(self._job, store, assets, media_id, batch_id, candidate)

    def retry(self, store: Any, assets: BookAssetStore, media_id: str, *, batch_id: str = "") -> bool:
        entry = store.get(media_id)
        if entry is None:
            return False
        if media_quota.is_settled_import(entry):
            # A learner's metered import that has settled would run Whisper again with no reservation: a new
            # import is a new admission (D-16S), never a re-run.
            return False
        with self._guard:
            if media_id in self._inflight:
                return True
        self.enqueue(store, assets, media_id, batch_id=batch_id or self.new_batch())
        return True

    def recover(self, store: Any, assets: BookAssetStore) -> int:
        """Re-queue what a restart interrupted. An item that keeps being interrupted stops after MAX_ATTEMPTS.

        A metered import (D-16S) also keeps its quota reservation across the restart: an interrupted job is
        re-queued and settles when it ends, and a job that ended but could not write its settlement (the quota
        store was down) writes it now, from the intent recorded on the entry."""
        count = 0
        try:
            entries = [*store.list(library="shared", status=None), *store.list(library="personal", status=None)]
        except Exception:  # noqa: BLE001 - an unreadable index is reported elsewhere
            return 0
        ready = media_quota.store_ready()
        for entry in entries:
            processing = dict(entry.processing or {})
            if media_quota.hold_of(entry) is not None and not ready:
                # A metered import waits for the quota store (wired after this runs in a process that starts it
                # early): nothing is dispatched, settled or slept on, and a later recover() takes it up.
                continue
            if processing.get("state") not in {STATE_QUEUED, STATE_RUNNING}:
                self._settle_quota(store, entry.media_id, media_quota.hold_of(entry), final=entry)
                continue
            if int(processing.get("attempts") or 0) >= MAX_ATTEMPTS:
                self._write_processing(store, entry, state=STATE_FAILED, stage=processing.get("stage") or STAGE_FETCH,
                                       reason="pipeline_interrupted", detail="Processing was interrupted too many times.",
                                       status="review")
                self._settle_quota(store, entry.media_id, media_quota.hold_of(entry))
                continue
            self.enqueue(store, assets, entry.media_id, batch_id=str(processing.get("batch_id") or self.new_batch()))
            count += 1
        return count

    def settle_pending(self, store: Any, limit: int = media_quota.INTENT_BATCH) -> int:
        """Write the settlements a finished metered import decided but the quota store could not take (an intent on
        the entry), bounded per call. Run on a timer in a process that stays up, so a settlement is never left for the
        reconciler's backstop (D-16S). Returns how many were attempted."""
        if not media_quota.store_ready():
            return 0
        try:
            entries = [*store.list(library="personal", status=None), *store.list(library="shared", status=None)]
        except Exception:  # noqa: BLE001 - an unreadable index is reported elsewhere
            return 0
        attempted = 0
        for entry in entries:
            if attempted >= limit:
                break
            hold = media_quota.hold_of(entry)
            if hold is None or (entry.processing or {}).get("state") in {STATE_QUEUED, STATE_RUNNING}:
                continue
            if media_quota.decode_intent(entry.source.get(media_quota.SOURCE_SETTLE, "")) is None:
                continue  # nothing decided yet: its job (or recover()) decides
            attempted += 1
            self._settle_quota(store, entry.media_id, hold, final=entry)
        return attempted

    # -- state --------------------------------------------------------------------------

    def _write_processing(self, store: Any, entry: MediaLibraryEntry, *, status: str | None = None, **fields: Any) -> MediaLibraryEntry:
        def change(fresh: MediaLibraryEntry) -> MediaLibraryEntry:
            if fresh.status == "archived" or ((fresh.processing or {}).get("state") == "cancelled" and fields.get("state") != STATE_QUEUED):
                raise PipelineStop("cancelled")
            processing = dict(fresh.processing or {})
            if fields.get("state") == STATE_RUNNING and processing.get("state") != STATE_RUNNING:
                processing["attempts"] = int(processing.get("attempts") or 0) + 1
            processing.update(fields)
            target_status = status
            if status == "published" and fresh.library == "shared":
                rights = str(fresh.source.get("rights") or RIGHTS_UNKNOWN)
                processing["rights"] = rights
                if rights != RIGHTS_CLEARED:
                    target_status = "review"
                    processing.update(state=STATE_HELD, reason="rights_unknown", auto_published=False)
            processing["updated_at"] = _now()
            return replace(fresh, processing=processing, **({"status": target_status} if target_status else {}))
        updated = store.update_if_present(entry.media_id, change)
        if updated is None:
            raise PipelineStop("cancelled")
        return updated

    # -- the job ------------------------------------------------------------------------

    def _job(self, store: Any, assets: BookAssetStore, media_id: str, batch_id: str, candidate: Candidate | None) -> None:
        # The reservation is read before anything runs: the learner may remove the entry while it is processing.
        first = store.get(media_id)
        hold = media_quota.hold_of(first)
        try:
            # An operator's shared import is not a learner's request: its provider calls are recorded without that origin.
            with telemetry_origin("learner" if first is None or first.library == "personal" else None):
                self._run(store, assets, media_id, batch_id, candidate)
        except PipelineStop as stop:
            if stop.code != "cancelled":
                self._hold_failed(store, media_id, stop)
        except Exception:  # noqa: BLE001 - the last line of defence; the item must say it failed
            _logger.exception("media pipeline crashed for %s", media_id)
            try:
                entry = store.get(media_id)
                if entry is not None:
                    self._write_processing(store, entry, state=STATE_FAILED, reason="pipeline_error",
                                           detail="The transcript pipeline failed unexpectedly. The server log has the details.",
                                           status="review")
            except Exception:  # noqa: BLE001
                _logger.exception("media pipeline could not record its own failure for %s", media_id)
        finally:
            self._settle_quota(store, media_id, hold)
            with self._guard:
                self._inflight.discard(media_id)

    def _dispatch_quota(self, entry: MediaLibraryEntry) -> None:
        """A metered import starts its first paid step only against a live reservation (fail closed)."""
        hold = media_quota.hold_of(entry)
        if hold is None:
            return
        try:
            media_quota.dispatch(hold)
        except media_quota.ImportQuotaUnavailable as refused:
            raise PipelineStop(refused.code) from None

    def _settle_quota(self, store: Any, media_id: str, hold: media_quota.EntryHold | None,
                      final: MediaLibraryEntry | None = None) -> None:
        """Settle a metered import by its operation id from where it ended (success: the source seconds; anything
        else: 0). Never raises: a settlement the store cannot take now is kept as an intent on the entry and written
        by the next `recover()`; the reconciler is only the last backstop."""
        if hold is None:
            return
        try:
            entry = final if final is not None else store.get(media_id)
            recorded = entry.source.get(media_quota.SOURCE_SETTLE, "") if entry is not None else ""
            pending = media_quota.decode_intent(recorded)
            actual, ref = pending if pending is not None else media_quota.settlement_for(entry, hold)
            if entry is not None and pending is None:
                self._mark_quota(store, media_id, media_quota.encode_intent(actual, ref))
            media_quota.settle(hold, actual, ref)
            self._mark_quota(store, media_id, media_quota.SETTLED)
            _logger.info("media import %s settled %s of %s source seconds (%s)", media_id, actual, hold.units, ref)
        except Exception:  # noqa: BLE001 - accounting never takes the pipeline down
            _logger.warning("media import quota not settled for %s; retried at the next recover()", media_id,
                            exc_info=True)

    @staticmethod
    def _mark_quota(store: Any, media_id: str, value: str) -> None:
        try:
            store.update_if_present(
                media_id, lambda fresh: replace(fresh, source={**fresh.source, media_quota.SOURCE_SETTLE: value}))
        except Exception:  # noqa: BLE001 - the marker is a convenience; the settlement itself is what counts
            _logger.warning("media import quota marker not written for %s", media_id, exc_info=True)

    def _run(self, store: Any, assets: BookAssetStore, media_id: str, batch_id: str, candidate: Candidate | None) -> None:
        entry = store.get(media_id)
        if entry is None:
            return
        language = entry.language
        personal = entry.library == "personal"
        try:
            entry = self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_FETCH, reason="", detail="", batch_id=batch_id, status="processing")
            self._dispatch_quota(entry)
            lines, origin, cost, asr_seconds, detected, words = self._transcript(store, assets, entry, batch_id, candidate)
        except PipelineStop as stop:
            self._hold_failed(store, media_id, stop)
            return
        entry = store.get(media_id) or entry
        entry = self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_SEGMENT)
        duration = int(entry.duration_ms or 0) or (lines[-1].end_ms if lines else 0)
        if duration:
            lines = _clamped(lines, duration)
        checks = validate_lines(lines, language=language, duration_ms=int(entry.duration_ms or 0), detected_language=detected)
        reason = first_failure(checks)
        public_checks = [{"id": check["id"], "pass": bool(check["pass"])} for check in checks]
        if reason:
            # A transcript was made and it is not usable. Keep what was made so an operator can see it; do not publish.
            entry = self._store_lesson(store, entry, lines, origin, duration, status="review", words=words)
            self._write_processing(store, entry, state=STATE_FAILED, stage=STAGE_SEGMENT, reason=reason,
                                   detail="", checks=public_checks, origin=origin, cost_usd=round(cost, 6), asr_seconds=round(asr_seconds, 1))
            return
        entry = self._store_lesson(store, entry, lines, origin, duration, status="processing", words=words)
        translation = self._translate(store, entry, batch_id, personal)
        entry = store.get(media_id) or entry
        rights = str(entry.source.get("rights") or RIGHTS_UNKNOWN)
        common = dict(checks=public_checks, origin=origin, cost_usd=round(cost, 6), asr_seconds=round(asr_seconds, 1),
                      translation=translation, rights=rights)
        if personal or rights == RIGHTS_CLEARED:
            # Readiness is when source artifacts are made, once (D-121); the model clip Compare measures is one (D-140).
            self._prepare_model_clips(assets, entry)
        if personal:
            self._write_processing(store, entry, state=STATE_READY, stage=STAGE_READY, reason="", detail="", auto_published=False, **common, status="published")
        elif rights == RIGHTS_CLEARED:
            self._write_processing(store, entry, state=STATE_READY, stage=STAGE_READY, reason="", detail="", auto_published=True, **common, status="published")
        else:
            self._write_processing(store, entry, state=STATE_HELD, stage=STAGE_READY, reason="rights_unknown", detail="", auto_published=False, **common, status="review")

    def _prepare_model_clips(self, assets: BookAssetStore, entry: MediaLibraryEntry) -> None:
        """Cut each speakable line's model clip once, from the source this item was admitted from.

        Idempotent (a stored clip is never cut again), bounded, provider-free, and never able to fail
        readiness: a lesson without clips is complete, and Compare says its model plot is unavailable.
        """
        if os.getenv("MEDIA_MODEL_CLIPS", "1").strip().casefold() in {"0", "false", "no", "off"}:
            return
        try:
            from writing_coach import model_clips
            from writing_coach.speaking_library import entry_clip_lines

            lesson = dict(entry.lesson or {})
            admitted = replace(entry, status="published", lesson={**lesson, "status": "PUBLISHED"})
            pending = model_clips.missing_lines(assets, entry_clip_lines(admitted))
            if not pending:
                return
            max_seconds = max_asr_seconds()
            with tempfile.TemporaryDirectory(prefix="orena-clips-") as directory:
                source = self._audio_source(assets, entry, Path(directory), max_seconds)
                result = model_clips.prepare_clips(
                    assets, source, pending,
                    max_lines=_env_int("MEDIA_MODEL_CLIP_MAX_LINES", model_clips.DEFAULT_MAX_LINES),
                    max_audio_ms=max_seconds * 1000,
                )
            _logger.info("model clips for %s: %s", entry.media_id, result.as_dict())
        except Exception:  # noqa: BLE001 - optional artifact; readiness stands without it
            _logger.warning("model clips could not be prepared for %s", entry.media_id, exc_info=True)

    def _hold_failed(self, store: Any, media_id: str, stop: PipelineStop) -> None:
        entry = store.get(media_id)
        if entry is None or entry.status == "archived" or stop.code == "cancelled":
            return
        self._write_processing(store, entry, state=STATE_FAILED, reason=stop.code, detail=stop.detail, status="review")

    def _store_lesson(self, store: Any, entry: MediaLibraryEntry, lines: list[Cue], origin: str, duration: int, *, status: str, words: list[SpeechAsrWord] | None = None) -> MediaLibraryEntry:
        transcript = build_transcript(entry.media_id, entry.language, lines)
        payload = lesson_payload(entry, transcript, origin, duration, words=words, english_reading=self._english_reading)
        existing = dict(entry.lesson or {})
        lesson = {
            **{key: value for key, value in existing.items() if key != "payload"},
            "lesson_id": entry.media_id,
            "payload": payload,
            "sections": ["new"],
            "status": "PUBLISHED" if status == "published" else "NEEDS_REVIEW",
            "curation": "automatic",
            "language": entry.language,
        }
        def change(fresh: MediaLibraryEntry) -> MediaLibraryEntry:
            if fresh.status == "archived" or (fresh.processing or {}).get("state") == "cancelled":
                raise PipelineStop("cancelled")
            return replace(fresh, lesson=lesson, duration_ms=int(fresh.duration_ms or 0) or duration, status=status)
        updated = store.update_if_present(entry.media_id, change)
        if updated is None:
            raise PipelineStop("cancelled")
        return updated

    # -- obtaining the transcript -------------------------------------------------------

    def _transcript(
        self, store: Any, assets: BookAssetStore, entry: MediaLibraryEntry, batch_id: str, candidate: Candidate | None
    ) -> tuple[list[Cue], str, float, float, str, list[SpeechAsrWord]]:
        language = entry.language
        cues: list[Cue] = []
        detected = ""
        if entry.provider == "youtube":
            cues = list(candidate.cues) if candidate is not None and candidate.cues else self._captions(entry)
            if cues:
                lines = segment_lines(cues, language)
                duration = int(entry.duration_ms or 0)
                if not first_failure(validate_lines(lines, language=language, duration_ms=duration)):
                    return lines, ORIGIN_CAPTION, 0.0, 0.0, "", []
                # Captions that are not good enough fall through to the audio (D-111 item 3).
        self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_TRANSCRIBE)
        raw, words, detected, cost, seconds = self._speech(store, assets, entry, batch_id)
        lines = segment_lines(raw, language)
        return lines, ORIGIN_ASR, cost, seconds, detected, words

    def _captions(self, entry: MediaLibraryEntry) -> list[Cue]:
        if self._ingestion is None or not entry.canonical_url:
            return []
        try:
            acquisition = self._ingestion.import_media(entry.canonical_url, "en", entry.language)
        except Exception:  # noqa: BLE001 - no captions is a normal answer; audio is the next source
            return []
        transcript = acquisition.media_object.transcript
        if transcript is None:
            return []
        return [Cue(int(segment.start_ms), int(segment.end_ms), segment.original_text) for segment in transcript.segments]

    def _speech(
        self, store: Any, assets: BookAssetStore, entry: MediaLibraryEntry, batch_id: str
    ) -> tuple[list[Cue], list[SpeechAsrWord], str, float, float]:
        if self._asr is None:
            raise PipelineStop("asr_unconfigured")
        max_seconds = max_asr_seconds()
        with tempfile.TemporaryDirectory(prefix="orena-asr-") as directory:
            work = Path(directory)
            source = self._audio_source(assets, entry, work, max_seconds)
            chunks = audio_chunks(source, work)
            total = sum(_probe_seconds(path) for path, _ in chunks)
            if total > max_seconds:
                raise PipelineStop("too_long", f"{int(total)}s")
            # A metered import listens to no more than the minutes it reserved: audio longer than the length read
            # at admission is not the source that was admitted, and nothing paid has started yet.
            reserved = media_quota.reserved_seconds(entry)
            if reserved is not None and total > reserved + media_quota.TOLERANCE_SECONDS:
                raise PipelineStop("duration_mismatch", f"{int(total)}s of {reserved}s")
            # Refuse before the first paid call when the whole item would pass a cap.
            try:
                self._ledger.check(KIND_ASR, batch_id, self._ledger.asr_estimate(total) if len(chunks) == 1 else self._ledger.asr_estimate(total))
            except SpendCapReached as capped:
                raise PipelineStop(capped.code, f"{capped.spent:.2f}/{capped.limit:.2f} USD") from capped
            results: list[tuple[SpeechAsrResult, float]] = []
            cost = 0.0
            for path, offset in chunks:
                estimate = self._ledger.asr_estimate(_probe_seconds(path))
                try:
                    self._ledger.check(KIND_ASR, batch_id, estimate)
                except SpendCapReached as capped:
                    raise PipelineStop(capped.code, f"{capped.spent:.2f}/{capped.limit:.2f} USD") from capped
                try:
                    result = self._asr.transcribe_bytes(
                        path.read_bytes(), filename=path.name, content_type="audio/mpeg", language=primary_language(entry.language) or None
                    )
                except SpeechAsrTimedOut as exc:
                    raise PipelineStop("asr_timeout") from exc
                except SpeechAsrRequestFailed as exc:
                    status = getattr(exc, "status_code", None)
                    code = "asr_rate_limited" if status == 429 else "asr_auth" if status in {401, 403} else "asr_failed"
                    raise PipelineStop(code) from exc
                except (SpeechAsrMalformed, SpeechAsrPayloadTooLarge) as exc:
                    raise PipelineStop("asr_failed") from exc
                # What was billed is the audio the provider processed, at least the provider's minimum.
                self._ledger.record(KIND_ASR, estimate, batch_id=batch_id, media_id=entry.media_id, units=_probe_seconds(path), provider="groq")
                cost += estimate
                results.append((result, offset))
        cues, words, detected = _asr_cues(results)
        if not cues:
            raise PipelineStop("empty_transcript")
        return cues, words, detected, cost, total

    def _audio_source(self, assets: BookAssetStore, entry: MediaLibraryEntry, work: Path, max_seconds: int) -> Path:
        if entry.provider == "youtube":
            if self._youtube_audio is None:
                raise PipelineStop("audio_unavailable")
            try:
                return Path(self._youtube_audio(entry.canonical_url, work, max_seconds=max_seconds))
            except PipelineStop:
                raise
            except Exception as exc:  # noqa: BLE001 - the provider refused or timed out; reported as one reason
                raise PipelineStop("audio_unavailable") from exc
        url = str((entry.playback or {}).get("url") or "")
        prefix = "/api/media/files/"
        if not url.startswith(prefix):
            raise PipelineStop("audio_unavailable")
        try:
            payload = assets.get(url[len(prefix):])
        except AssetNotFound as exc:
            raise PipelineStop("audio_unavailable") from exc
        suffix = Path(url).suffix or ".bin"
        source = work / f"source{suffix}"
        source.write_bytes(payload)
        return source

    # -- meaning --------------------------------------------------------------------------

    def _translate(self, store: Any, entry: MediaLibraryEntry, batch_id: str, personal: bool) -> str:
        """Materialize configured optional meanings before admission; workspace reads never generate them."""
        languages = [item.strip().casefold() for item in os.getenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi").split(",") if item.strip()]
        languages = [item for item in languages if item != primary_language(entry.language)]
        if not languages or self._meanings is None:
            return "deferred"
        self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_TRANSLATE)
        characters = sum(len(line.text) for line in lines_from_payload((entry.lesson or {}).get("payload")))
        spent = 0.0
        outcome = "ready"
        for target in languages:
            tokens = max(200, int(characters / 2.5)) + 200
            estimate = self._ai_cost("", {"prompt_tokens": tokens, "completion_tokens": tokens})
            try:
                self._ledger.check(KIND_AI, batch_id, estimate)
            except SpendCapReached:
                return "spend_cap"
            usage: list[tuple[str, Any]] = []
            try:
                if self._translation_sink is not None:
                    with self._translation_sink(lambda model, value, captured=usage: captured.append((model, value))):
                        result = self._meanings(entry, target)
                else:
                    result = self._meanings(entry, target)
            except Exception:  # noqa: BLE001 - translation is enrichment; the lesson stands without it
                _logger.warning("pre-translation failed for %s", entry.media_id, exc_info=True)
                outcome = "failed"
                continue
            actual = sum(self._ai_cost(model, value) for model, value in usage)
            if usage or getattr(result, "provider_calls", 0):
                actual = actual or estimate
                self._ledger.record(KIND_AI, actual, batch_id=batch_id, media_id=entry.media_id, units=len(usage), provider="groq")
                spent += actual
            if getattr(result, "status", "ready") not in {"ready", "not_required"}:
                outcome = "failed"
        return outcome

    def _ai_cost(self, model: str, usage: Any) -> float:
        usage = usage if isinstance(usage, Mapping) else {}
        priced = estimate_token_cost("groq", model, usage)
        if priced.get("state") == "estimated" and isinstance(priced.get("amount"), (int, float)):
            return float(priced["amount"])
        tokens = sum(int(usage.get(key) or 0) for key in ("prompt_tokens", "completion_tokens", "total_tokens") if isinstance(usage.get(key), int))
        if usage.get("total_tokens") and usage.get("prompt_tokens") is not None:
            tokens = int(usage.get("total_tokens") or 0)
        return tokens / 1_000_000 * self._ledger.ai_usd_per_million_tokens()


def _clamped(lines: list[Cue], duration_ms: int) -> list[Cue]:
    clipped: list[Cue] = []
    for line in lines:
        if line.start_ms >= duration_ms:
            continue
        clipped.append(Cue(line.start_ms, min(line.end_ms, duration_ms), line.text) if line.end_ms > line.start_ms else line)
    return [line for line in clipped if line.end_ms > line.start_ms]


def lesson_payload(entry: MediaLibraryEntry, transcript: MediaTranscript, origin: str, duration_ms: int, *, words: list[SpeechAsrWord] | None = None, english_reading: Callable[[str], str] | None = None) -> dict[str, Any]:
    """The stored acquisition payload the Listening room already reads, built from the pipeline's transcript."""
    from writing_coach.media_meaning import pinyin_for_segments
    from writing_coach.pinyin_alignment import align_readings

    pinyin = dict(pinyin_for_segments(transcript.segments)) if primary_language(entry.language) == "zh" else {}
    readings = {}
    if primary_language(entry.language) == "en" and english_reading:
        import re

        vocabulary = {}
        for segment in transcript.segments:
            projected = []
            for match in re.finditer(r"[^\W_]+(?:['’-][^\W_]+)*", segment.original_text):
                key = match.group().casefold()
                if key not in vocabulary:
                    try:
                        vocabulary[key] = english_reading(match.group()) or ""
                    except Exception:
                        vocabulary[key] = ""
                if vocabulary[key]:
                    projected.append({"text": match.group(), "start": match.start(), "end": match.end(), "reading": vocabulary[key]})
            readings[segment.segment_id] = projected
    return {
        "asset": {
            "asset_id": entry.media_id,
            "source_url": entry.canonical_url,
            "source_provider": entry.provider,
            "source_type": "external-video" if entry.provider == "youtube" else "imported-media",
            "title": entry.title,
            "source_language": entry.language,
            "processing_state": "ready",
            "duration_ms": duration_ms or None,
            "transcript_available": True,
            "translation_available": False,
            "thumbnail_url": "",
        },
        "playback": dict(entry.playback),
        "transcript": {
            "asset_id": transcript.asset_id,
            "source_language": transcript.source_language,
            "segments": [
                {
                    "segment_id": segment.segment_id,
                    "order": segment.order,
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "original_text": segment.original_text,
                    "words": [
                        {"text": word.word, "start_ms": word.start_ms, "end_ms": word.end_ms}
                        for word in words or ()
                        if word.start_ms >= segment.start_ms and word.end_ms <= segment.end_ms
                    ],
                }
                for segment in transcript.segments
            ],
        },
        "transcript_origin": origin,
        "translations": [],
        "catalog": {
            "readings_by_segment": readings,
            "pinyin_by_segment": pinyin,
            "pinyin_chars_by_segment": align_readings(transcript.segments, pinyin) if pinyin else {},
        },
    }
