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
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from writing_coach import media_quota, media_translation
from writing_coach.ai.audio_telemetry import telemetry_origin
from writing_coach.billing.funding_context import system_funding
from writing_coach.ai.pricing import estimate_token_cost
from writing_coach.book_asset_store import AssetNotFound, BookAssetStore
from writing_coach.media_learning import MediaTranscript, TranscriptSegment
from writing_coach.media_library_store import MediaLibraryEntry
from writing_coach.media_asr_filter import screen_segments
from writing_coach.media_zh_cleanup import clean_asr_cues, normalise_words
from writing_coach.media_segmentation import Cue, first_failure, primary_language, segment_lines, validate_lines
from writing_coach.media_spend import KIND_AI, KIND_ASR, SpendCapReached, SpendLedger
from writing_coach.speech_asr import (
    SpeechAsrMalformed,
    SpeechAsrPayloadTooLarge,
    SpeechAsrRequestFailed,
    SpeechAsrResult,
    SpeechAsrSegment,
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

# What an import may do when the provider's captions cannot be had (D-214). `captions_or_asr` (the default, and what an
# item with no policy means) listens to the audio instead; `captions_only` stops there, before any audio download or
# speech recognition, so nothing is spent. Stored on the item's `source`, so a re-run keeps it.
SOURCE_TRANSCRIPT_POLICY = "transcript_policy"
POLICY_DEFAULT = "captions_or_asr"
POLICY_CAPTIONS_ONLY = "captions_only"
TRANSCRIPT_POLICIES = (POLICY_DEFAULT, POLICY_CAPTIONS_ONLY)

CHUNK_SECONDS = 600
MAX_ATTEMPTS = 3
AUDIO_FORMAT_TIMEOUT = 600

# Translation continues the lines still missing, boundedly (Video PR-A): at most this many provider rounds per language
# (the first plus continuations), each wait capped, and the waits together capped, so a stuck provider cannot hold the
# single worker. Every round stays under the AI spend cap and only the missing lines are requested again.
TRANSLATION_MAX_ROUNDS = 5
TRANSLATION_MAX_WAIT = 60.0
TRANSLATION_MAX_TOTAL_WAIT = 150.0
TRANSLATION_DEFAULT_BACKOFF = 5.0
# A failure that asking again cannot fix.
TRANSLATION_TERMINAL_REASONS = frozenset({"spend_cap", "provider_auth", "not_configured", "too_large", "request_too_large"})

# A transcript still short of lines after those rounds is resumed later, not abandoned (D-211). The provider's
# per-minute token allowance refills in about a minute (8000 tokens a minute on the trial key, `docs/ORENA_AI_COST_
# REDUCTION_PLAN.md`; one 24-line request reserves about 2.8k of them), so a deferred continuation waits what the provider
# asked, then asks for only the lines still missing. Bounded three ways: attempts, a total time from the first deferral,
# and one wait; a longer wait (a daily allowance) is not scheduled at all. Rounds inside a continuation do not sleep: the
# schedule is the wait. Every round still checks the AI spend cap, and the same single worker runs it.
CONTINUATION_MAX_ATTEMPTS = 6
CONTINUATION_BUDGET_SECONDS = 1800.0
CONTINUATION_MIN_DELAY = 20.0
CONTINUATION_DEFAULT_DELAY = 65.0
# One wait may be as long as the provider asked, up to this. D-211 set 300 s; the 2026-10-15 trial's 429 asked for 521 s (the
# per-minute token bucket resets in about 58 s, so the longer ask is another allowance) and no continuation was armed. 900 s
# fits the 1800 s budget; a wait beyond it (a daily allowance asks for hours) is still never promised (D-214).
CONTINUATION_MAX_DELAY = 900.0
# The stable reason recorded when the provider asked for longer than that (`processing.translation_retry_after` has the ask).
REASON_LONG_WAIT = "rate_limited_long_wait"
CONTINUATION_ROUNDS = 2


# The stable reason codes an item can be held or failed with, each with the English sentence stored beside it
# (`processing["message"]`) for anything that reads the record directly. The console words each code itself, in the
# operator's language (`impErr_<code>`); a code not listed here has no stored message, never a made-up one.
REASON_MESSAGES: dict[str, str] = {
    "rights_unknown": "The transcript is ready; rights are unknown, so it is held until a person confirms them.",
    "audio_unavailable": "The audio of this source could not be downloaded.",
    "captions_blocked": "The provider refused to give the captions, and the audio could not be downloaded either.",
    "asr_unconfigured": "Speech recognition is not configured on this deployment.",
    "asr_timeout": "Speech recognition did not answer in time.",
    "asr_rate_limited": "Speech recognition is rate limited right now.",
    "asr_auth": "Speech recognition refused this deployment's credentials.",
    "asr_failed": "Speech recognition could not transcribe this audio.",
    "empty_transcript": "No speech was found in this source.",
    "language_mismatch": "The speech is not in the language this item was imported as.",
    "coverage_low": "The transcript covers too little of the recording.",
    "segments_invalid": "The transcript could not be cut into usable lines.",
    "repetition": "The transcript is mostly repeated text.",
    "too_long": "This source is longer than the processing limit.",
    "duration_mismatch": "The audio is longer than the length reserved when it was imported.",
    "pipeline_interrupted": "Processing was interrupted too many times.",
    "pipeline_error": "The transcript pipeline failed unexpectedly. The server log has the details.",
    "captions_unavailable": "The provider's captions could not be fetched this time. Speech recognition was not run; any stored captions were kept.",
    "captions_unusable": "The provider's captions were not good enough to use. Speech recognition was not run; any stored captions were kept.",
    "caption_quota": "Today's limit of caption requests to the caption provider was reached; none was sent.",
    "spend_cap_day": "The daily processing spend limit was reached.",
    "spend_cap_batch_asr": "The speech recognition spend limit for this batch was reached.",
    "spend_cap_batch_ai": "The AI spend limit for this batch was reached.",
}


def reason_message(code: str) -> str:
    return REASON_MESSAGES.get(str(code or ""), "")


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
    from writing_coach import policies

    return int(policies.value("media.asr_max_seconds"))


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


def _asr_cues(results: list[tuple[SpeechAsrResult, float]], language: str = "") -> tuple[list[Cue], list[SpeechAsrWord], str, dict[str, int]]:
    """(cues, words, detected language, {"filtered", "flagged"}): the recogniser's segments joined across chunks,
    with hallucinated segments and the words inside them removed (media_asr_filter)."""
    segments: list[SpeechAsrSegment] = []
    words: list[SpeechAsrWord] = []
    detected = ""
    for result, offset in results:
        shift = round(offset * 1000)
        detected = detected or result.language
        for segment in result.segments:
            segments.append(replace(segment, start_ms=segment.start_ms + shift, end_ms=segment.end_ms + shift))
        if not result.segments and result.text.strip():
            # A provider that returned text without segments: one cue spanning the chunk's words, if it has them.
            if result.words:
                segments.append(SpeechAsrSegment(result.text, result.words[0].start_ms + shift, result.words[-1].end_ms + shift))
        for word in result.words:
            words.append(SpeechAsrWord(word.word, word.start_ms + shift, word.end_ms + shift))
    screen = screen_segments(segments, words, language or detected)
    cues = [Cue(segment.start_ms, segment.end_ms, segment.text) for segment in screen.segments]
    return cues, list(screen.words), detected, {"filtered": screen.filtered, "flagged": screen.flagged}


def _screen_fields(screen: dict[str, int]) -> dict[str, int]:
    """What the ASR screen removed or doubted, recorded so a reviewer sees it (empty for a caption transcript)."""
    return {"asr_filtered": int(screen["filtered"]), "asr_flagged": int(screen["flagged"])} if screen else {}


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
        admin_ingestion: Any = None,
        youtube_audio: Callable[..., Path] | None = None,
        meanings: Callable[[MediaLibraryEntry, str], Any] | None = None,
        english_reading: Callable[[str], str] | None = None,
        workers: int | None = None,
        translation_sink: Callable[[Callable[[str, Any], None]], Any] | None = None,
    ) -> None:
        self._ledger = ledger
        self._asr = asr
        self._ingestion = ingestion
        self._admin_ingestion = admin_ingestion   # an operator's (shared) item may take captions from Supadata (D-215)
        self._youtube_audio = youtube_audio
        self._meanings = meanings
        self._english_reading = english_reading
        # Where a translation call reports the tokens it was billed; the provider's own sink unless a caller brings one.
        self._translation_sink = translation_sink if translation_sink is not None else media_translation.usage_sink
        self._sleep: Callable[[float], None] = time.sleep
        self._clock: Callable[[], float] = time.time
        # (delay seconds, callback): a one-shot timer; the work itself runs on the pool below. Replaced in tests.
        self._schedule: Callable[[float, Callable[[], None]], None] = self._timer_schedule
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
            # import is a new admission (D-168), never a re-run.
            return False
        with self._guard:
            if media_id in self._inflight:
                return True
        self._remember_previous(store, entry)
        self.enqueue(store, assets, media_id, batch_id=batch_id or self.new_batch())
        return True

    # -- a reprocess never destroys a good item ---------------------------------------------

    @staticmethod
    def _remember_previous(store: Any, entry: MediaLibraryEntry) -> None:
        """Before a re-run starts: keep what a good item looked like (ready or held, with a transcript that passed), so a
        re-run that fails at any step puts it back instead of leaving `failed` beside a transcript that is fine."""
        processing = dict(entry.processing or {})
        if processing.get("state") not in {STATE_READY, STATE_HELD} or not usable_transcript(entry)[0]:
            return

        def change(fresh: MediaLibraryEntry) -> MediaLibraryEntry:
            current = dict(fresh.processing or {})
            if current.get("state") not in {STATE_READY, STATE_HELD}:
                return fresh
            snapshot = {key: value for key, value in current.items() if key not in {"previous", "attempts", "updated_at"}}
            snapshot["_status"] = fresh.status
            return replace(fresh, processing={**current, "previous": snapshot})
        try:
            store.update_if_present(entry.media_id, change)
        except Exception:  # noqa: BLE001 - without the snapshot a failed re-run behaves as it always did
            _logger.warning("previous state not kept for %s", entry.media_id, exc_info=True)

    def _restore_previous(self, store: Any, media_id: str, reason: str, detail: str = "") -> bool:
        """A re-run of a good item failed: put the item back as it was and record why the re-run did not happen.
        False when the item has no snapshot (a first import), so the caller fails it as before."""
        restored: list[bool] = []

        def change(fresh: MediaLibraryEntry) -> MediaLibraryEntry:
            current = dict(fresh.processing or {})
            snapshot = current.get("previous")
            if fresh.status == "archived" or current.get("state") == "cancelled" or not isinstance(snapshot, Mapping) or not snapshot:
                return fresh
            kept = {key: value for key, value in snapshot.items() if key != "_status"}
            kept.update(attempts=current.get("attempts", 0), updated_at=_now(), reprocess_reason=reason, reprocess_detail=detail,
                        reprocess_message=reason_message(reason), previous={})
            restored.append(True)
            return replace(fresh, processing=kept, status=str(snapshot.get("_status") or fresh.status))
        try:
            store.update_if_present(media_id, change)
        except Exception:  # noqa: BLE001
            _logger.warning("previous state not restored for %s", media_id, exc_info=True)
            return False
        if restored:
            # The snapshot may hold a pending translation continuation; the run cleared its timer, so arm it again.
            fresh = store.get(media_id)
            if fresh is not None:
                self._rearm_continuation(store, fresh)
        return bool(restored)

    @staticmethod
    def _clear_previous(store: Any, media_id: str) -> None:
        """A run that was cancelled (archive) leaves no snapshot behind to be reused by a later re-run."""
        def change(fresh: MediaLibraryEntry) -> MediaLibraryEntry:
            current = dict(fresh.processing or {})
            if not current.get("previous"):
                return fresh
            return replace(fresh, processing={**current, "previous": {}})
        try:
            store.update_if_present(media_id, change)
        except Exception:  # noqa: BLE001
            _logger.warning("previous state not cleared for %s", media_id, exc_info=True)

    def recover(self, store: Any, assets: BookAssetStore) -> int:
        """Re-queue what a restart interrupted. An item that keeps being interrupted stops after MAX_ATTEMPTS.

        A metered import (D-168) also keeps its quota reservation across the restart: an interrupted job is
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
                self._rearm_continuation(store, entry)
                continue
            if int(processing.get("attempts") or 0) >= MAX_ATTEMPTS:
                if self._restore_previous(store, entry.media_id, "pipeline_interrupted"):
                    self._settle_quota(store, entry.media_id, media_quota.hold_of(entry))
                    continue
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
        reconciler's backstop (D-168). Returns how many were attempted."""
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
            if "reason" in fields or processing.get("reason"):
                # Stored beside the code so the record says it in words; a code without a message keeps none.
                processing["message"] = reason_message(processing.get("reason", ""))
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
            # PR-MON-6 §2: a media batch is system-funded, bounded by the media spend caps (media_spend.py); a
            # learner's import was admitted on its allowance (media.import is allowance-only, H-5).
            with telemetry_origin("learner" if first is None or first.library == "personal" else None), \
                    system_funding("media_pipeline"):
                self._run(store, assets, media_id, batch_id, candidate)
        except PipelineStop as stop:
            self._hold_failed(store, media_id, stop)
        except Exception:  # noqa: BLE001 - the last line of defence; the item must say it failed
            _logger.exception("media pipeline crashed for %s", media_id)
            try:
                entry = store.get(media_id)
                if entry is not None and not self._restore_previous(store, media_id, "pipeline_error"):
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
            entry = self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_FETCH, reason="", detail="", batch_id=batch_id, status="processing",
                                           translation="", translation_counts={}, translation_reason="", translation_retry_after=0, translation_continuation={}, asr_filtered=0, asr_flagged=0,
                                           caption_kind="", caption_provider="", caption_language="", caption_fallback="", reprocess_reason="", reprocess_detail="", reprocess_message="")
            self._dispatch_quota(entry)
            lines, origin, cost, asr_seconds, detected, words, screen = self._transcript(store, assets, entry, batch_id, candidate)
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
            if self._restore_previous(store, media_id, reason):
                return  # the item had a good transcript; the new one is not kept over it
            # A transcript was made and it is not usable. Keep what was made so an operator can see it; do not publish.
            entry = self._store_lesson(store, entry, lines, origin, duration, status="review", words=words)
            self._write_processing(store, entry, state=STATE_FAILED, stage=STAGE_SEGMENT, reason=reason,
                                   detail="", checks=public_checks, origin=origin, cost_usd=round(cost, 6), asr_seconds=round(asr_seconds, 1),
                                   **_screen_fields(screen))
            return
        entry = self._store_lesson(store, entry, lines, origin, duration, status="processing", words=words)
        stop: dict[str, Any] = {}
        translation, translation_counts = self._translate(store, entry, batch_id, personal, stop=stop)
        translation = self._defer_translation(store, entry, translation, stop)
        entry = store.get(media_id) or entry
        rights = str(entry.source.get("rights") or RIGHTS_UNKNOWN)
        common = dict(previous={}, checks=public_checks, origin=origin, cost_usd=round(cost, 6), asr_seconds=round(asr_seconds, 1),
                      translation=translation, translation_counts=translation_counts, rights=rights, **_screen_fields(screen))
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
        from writing_coach import policies

        if not policies.value("media.model_clips_enabled"):
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
                    max_lines=int(policies.value("media.model_clip_max_lines")),
                    max_audio_ms=max_seconds * 1000,
                )
            _logger.info("model clips for %s: %s", entry.media_id, result.as_dict())
        except Exception:  # noqa: BLE001 - optional artifact; readiness stands without it
            _logger.warning("model clips could not be prepared for %s", entry.media_id, exc_info=True)

    def _hold_failed(self, store: Any, media_id: str, stop: PipelineStop) -> None:
        entry = store.get(media_id)
        if entry is None:
            return
        if entry.status == "archived" or stop.code == "cancelled":
            self._clear_previous(store, media_id)
            return
        if self._restore_previous(store, media_id, stop.code, stop.detail):
            return
        self._write_processing(store, entry, state=STATE_FAILED, reason=stop.code, detail=stop.detail, status="review", previous={})

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
            # The origin is recorded with the payload that carries it, in one write, so the two never disagree (D-213).
            processing = {**dict(fresh.processing or {}), "origin": origin} if fresh.processing is not None else fresh.processing
            return replace(fresh, lesson=lesson, processing=processing, duration_ms=int(fresh.duration_ms or 0) or duration, status=status)
        updated = store.update_if_present(entry.media_id, change)
        if updated is None:
            raise PipelineStop("cancelled")
        return updated

    # -- obtaining the transcript -------------------------------------------------------

    def _transcript(
        self, store: Any, assets: BookAssetStore, entry: MediaLibraryEntry, batch_id: str, candidate: Candidate | None
    ) -> tuple[list[Cue], str, float, float, str, list[SpeechAsrWord], dict[str, int]]:
        language = entry.language
        cues: list[Cue] = []
        detected = ""
        captions_error = ""
        fallback = ""  # why the audio is used where captions were the first choice (D-213), a stable code
        if entry.provider == "youtube":
            kind = str(entry.source.get("caption_kind") or "")
            provider = str(entry.source.get("caption_provider") or "")
            caption_language = str(entry.source.get("caption_language") or "")
            if candidate is not None and candidate.cues:
                cues = list(candidate.cues)
            else:
                cues, captions_error, kind, provider, caption_language = self._captions(entry)
                if not cues and not captions_error and entry.source.get("caption_status") == "unavailable":
                    # the importer was refused by the provider and said so (or by the daily caption cap, D-215)
                    captions_error = str(entry.source.get("caption_error") or "") or "provider_failure"
            if cues:
                lines = segment_lines(cues, language)
                duration = int(entry.duration_ms or 0)
                if not first_failure(validate_lines(lines, language=language, duration_ms=duration)):
                    self._write_processing(store, entry, caption_kind=kind, caption_provider=provider,
                                           caption_language=caption_language, caption_fallback="")
                    return lines, ORIGIN_CAPTION, 0.0, 0.0, "", [], {}
                # Captions that are not good enough fall through to the audio (D-111 item 3).
                fallback = "captions_unusable"
            elif captions_error:
                fallback = "caption_quota" if captions_error == "caption_quota" else "captions_unavailable"
            if self._keeps_captions(entry):
                # The stored transcript is the provider's own captions and they cannot be had now: it stays, and the
                # audio is not listened to in its place (D-213). The item is restored by the caller.
                raise PipelineStop(fallback or "captions_unavailable", captions_error)
            if entry.source.get(SOURCE_TRANSCRIPT_POLICY) == POLICY_CAPTIONS_ONLY:
                # The operator asked for captions or nothing (D-214): no audio is downloaded, no recognition runs, nothing
                # is spent. The item fails with the stable reason and can be re-run once the provider answers.
                raise PipelineStop(fallback or "captions_unavailable", captions_error)
        self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_TRANSCRIBE, caption_kind="", caption_provider="",
                               caption_language="", caption_fallback=fallback)
        try:
            raw, words, detected, cost, seconds, screen = self._speech(store, assets, entry, batch_id)
        except PipelineStop as stop:
            # Captions were refused by the provider (not merely absent) and the audio route is closed too: that is the
            # cause an operator can act on, with the audio failure kept in the detail.
            if stop.code == "audio_unavailable" and captions_error in {"provider_failure", "provider_timeout"}:
                raise PipelineStop("captions_blocked", "audio_unavailable") from stop
            raise
        # Chinese recognition output is repaired (no spaces between Hanzi, sentence marks, no leading silence) before it is cut.
        raw = clean_asr_cues(raw, words, language or detected)
        words = normalise_words(words, language or detected)  # the same script as the lines, so taps stay aligned
        lines = segment_lines(raw, language)
        return lines, ORIGIN_ASR, cost, seconds, detected, words, screen

    def _captions(self, entry: MediaLibraryEntry) -> tuple[list[Cue], str, str, str, str]:
        """(cues, why-none, kind, provider, language): the provider's category when it failed, "" when there were simply no
        captions; `kind` is `manual`, `auto` or `unknown` for the track that was used; `provider` is empty for YouTube's own
        captions and `supadata` for a track from there, with the language it returned (D-215)."""
        service = self._admin_ingestion if self._admin_ingestion is not None and entry.library == "shared" else self._ingestion
        if service is None or not entry.canonical_url:
            return [], "", "", "", ""
        try:
            acquisition = service.import_media(entry.canonical_url, "en", entry.language)
        except Exception as exc:  # noqa: BLE001 - no captions is a normal answer; audio is the next source
            return [], str(getattr(getattr(exc, "category", None), "value", "") or ""), "", "", ""
        provenance = getattr(acquisition, "provenance", None) or {}
        transcript = acquisition.media_object.transcript
        if transcript is None:
            refused = provenance.get("caption_status") == "unavailable"
            return [], (str(provenance.get("caption_error") or "provider_failure") if refused else ""), "", "", ""
        return ([Cue(int(segment.start_ms), int(segment.end_ms), segment.original_text) for segment in transcript.segments], "",
                str(provenance.get("caption_kind") or ""), str(provenance.get("caption_provider") or ""),
                str(provenance.get("caption_language") or ""))

    @staticmethod
    def _keeps_captions(entry: MediaLibraryEntry) -> bool:
        """A re-run of an item whose stored transcript is the provider's captions (it was snapshotted as good)."""
        previous = (entry.processing or {}).get("previous")
        if not isinstance(previous, Mapping) or not previous:
            return False
        payload = (entry.lesson or {}).get("payload") or {}
        return (payload.get("transcript_origin") or previous.get("origin")) == ORIGIN_CAPTION

    def _speech(
        self, store: Any, assets: BookAssetStore, entry: MediaLibraryEntry, batch_id: str
    ) -> tuple[list[Cue], list[SpeechAsrWord], str, float, float, dict[str, int]]:
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
        cues, words, detected, screen = _asr_cues(results, entry.language)
        if not cues:
            raise PipelineStop("empty_transcript", f"{screen['filtered']} filtered" if screen["filtered"] else "")
        return cues, words, detected, cost, total, screen

    def _audio_source(self, assets: BookAssetStore, entry: MediaLibraryEntry, work: Path, max_seconds: int) -> Path:
        if entry.provider == "youtube":
            if self._youtube_audio is None:
                raise PipelineStop("audio_unavailable")
            try:
                return Path(self._youtube_audio(entry.canonical_url, work, max_seconds=max_seconds))
            except PipelineStop:
                raise
            except Exception as exc:  # noqa: BLE001 - the provider refused or timed out; reported as one reason
                _logger.warning("audio download failed for %s: %s: %s", entry.media_id, type(exc).__name__, " ".join(str(exc).split())[:200])
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

    def _translate(
        self, store: Any, entry: MediaLibraryEntry, batch_id: str, personal: bool, *, stop: dict[str, Any] | None = None,
        resume: bool = False, max_rounds: int = TRANSLATION_MAX_ROUNDS, max_total_wait: float = TRANSLATION_MAX_TOTAL_WAIT,
        guard: Callable[[], None] | None = None,
    ) -> tuple[str, dict[str, dict[str, int]]]:
        """Materialize configured optional meanings before admission; workspace reads never generate them.

        Returns (outcome, counts). The outcome is `ready`, `deferred`, `spend_cap`, `partial` (some lines have a meaning,
        some do not: the learner sees the ones that exist) or `failed` (none). Counts are per language, `{done, total}`.
        A partial or failed translation never changes the item's own state: the lesson stands without it.

        `stop`, when given, receives why the run ended (`reason`, the provider's `retry_after`) for the caller that may
        defer the rest. `resume` is a continuation: the item's own state is left alone (a held item stays held). `guard`, when given, is
        called before every provider round and raises `PipelineStop` when the item has been archived, removed or re-run."""
        languages = [item.strip().casefold() for item in os.getenv("MEDIA_PRETRANSLATE_LANGUAGES", "vi").split(",") if item.strip()]
        languages = [item for item in languages if item != primary_language(entry.language)]
        if not languages or self._meanings is None:
            return "deferred", {}
        if not resume:
            self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_TRANSLATE)
        stored_lines = lines_from_payload((entry.lesson or {}).get("payload"))
        characters = sum(len(line.text) for line in stored_lines)
        total_lines = len(stored_lines)
        counts: dict[str, dict[str, int]] = {}
        incomplete = False
        any_done = False
        stop_reason = ""
        last_retry_after = 0.0
        waited = 0.0
        for target in languages:
            done = 0
            for attempt in range(max_rounds):
                missing_share = max(1, total_lines - done) / max(1, total_lines)
                tokens = max(200, int(characters * missing_share / 2.5)) + 200
                estimate = self._ai_cost("", {"prompt_tokens": tokens, "completion_tokens": tokens})
                try:
                    self._ledger.check(KIND_AI, batch_id, estimate)
                except SpendCapReached:
                    stop_reason = "spend_cap"
                    if attempt == 0:
                        self._record_translation_reason(store, entry, stop_reason)
                        if stop is not None:
                            stop.update(reason=stop_reason, retry_after=0.0)
                        return "spend_cap", counts
                    break
                if guard is not None:
                    guard()
                usage: list[tuple[str, Any]] = []
                retry_after = 0.0
                try:
                    if self._translation_sink is not None:
                        with self._translation_sink(lambda model, value, captured=usage: captured.append((model, value))):
                            result = self._meanings(entry, target)
                    else:
                        result = self._meanings(entry, target)
                except Exception:  # noqa: BLE001 - translation is enrichment; the lesson stands without it
                    _logger.warning("pre-translation failed for %s", entry.media_id, exc_info=True)
                    stop_reason = "provider_error"
                    counts[target] = {"done": done, "total": total_lines}
                    result = None
                if usage:
                    # Only what the provider reported it billed (#228): a refused call (401/403/429), a timeout and an
                    # answer without `usage` carry none, so a round that made no progress costs nothing. `estimate` stays
                    # what the cap is checked against before the call, never what is booked after it.
                    actual = sum(self._ai_cost(model, value) for model, value in usage)
                    self._ledger.record(KIND_AI, actual, batch_id=batch_id, media_id=entry.media_id, units=len(usage), provider="groq")
                if result is not None:
                    if getattr(result, "status", "ready") in {"ready", "not_required"}:
                        done = total_lines
                        stop_reason = ""
                        counts[target] = {"done": done, "total": total_lines}
                        break
                    progressed = len(getattr(result, "meanings", ()) or ()) > done
                    done = max(done, len(getattr(result, "meanings", ()) or ()))
                    counts[target] = {"done": done, "total": total_lines}
                    given = str(getattr(result, "reason", "") or "")
                    stop_reason = given or ("incomplete" if progressed else "provider_error")
                    retry_after = float(getattr(result, "retry_after", 0.0) or 0.0)
                    last_retry_after = retry_after
                    if stop_reason == "rate_limited":
                        _logger.warning("media translation rate limited for %s (%s): retry_after=%.0f s, %d of %d lines",
                                        entry.media_id, target, retry_after, done, total_lines)
                    # A partial that did not grow and says nothing would be asked for again with no new information.
                    if not progressed and not given:
                        break
                if stop_reason in TRANSLATION_TERMINAL_REASONS or attempt == max_rounds - 1:
                    break
                # The provider asked for longer than one wait may be: asking again now meets the same limit.
                if stop_reason == "rate_limited" and retry_after > TRANSLATION_MAX_WAIT:
                    break
                # A rate limit is waited out as the provider asked (capped); otherwise a short fixed pause. A round that
                # made progress needs none.
                wait = 0.0
                if result is None or stop_reason != "incomplete":
                    wait = min(retry_after or TRANSLATION_DEFAULT_BACKOFF, TRANSLATION_MAX_WAIT)
                if waited + wait > max_total_wait:
                    break
                if wait:
                    waited += wait
                    self._sleep(wait)
            counts.setdefault(target, {"done": done, "total": total_lines})
            if done < total_lines or not total_lines and stop_reason:
                incomplete = True
            any_done = any_done or done > 0
        self._record_translation_reason(store, entry, stop_reason if incomplete else "")
        if stop is not None:
            stop.update(reason=stop_reason if incomplete else "", retry_after=last_retry_after)
        if not incomplete:
            return "ready", counts
        return ("partial" if any_done else "failed"), counts

    # -- translation only (D-213) ---------------------------------------------------------------------

    def retry_translation(self, store: Any, media_id: str) -> str:
        """Ask again for the lines still without a meaning, and nothing else: the transcript, its origin, the item's state
        and its status are not touched. Returns `queued`, `busy` (the item is being worked), `missing` or `no_transcript`.
        A restarted budget: the automatic continuation of D-211 may have ended, and this is the operator starting it over."""
        entry = store.get(media_id)
        if entry is None or entry.status == "archived" or (entry.processing or {}).get("state") == "cancelled":
            return "missing"
        if (entry.processing or {}).get("state") in {STATE_QUEUED, STATE_RUNNING}:
            return "busy"
        if not usable_transcript(entry)[0]:
            return "no_transcript"
        with self._guard:
            if media_id in self._inflight:
                return "busy"
            self._inflight.add(media_id)
        try:
            # The previous run's outcome and refusal are cleared as the retry is queued: until it has run, the item must not
            # present an old `provider_auth` or `rate_limited` as the result of this request (D-217). The lines already
            # translated (`translation_counts`) stay; the job writes the new outcome and reason when it ends.
            self._write_processing(store, entry, translation_continuation={}, translation="", translation_reason="", translation_retry_after=0)
        except PipelineStop:
            with self._guard:
                self._inflight.discard(media_id)
            return "missing"
        if os.getenv("MEDIA_PIPELINE_INLINE", "").strip() in {"1", "true", "yes"}:
            self._translation_only_job(store, media_id)
        else:
            self._pool.submit(self._translation_only_job, store, media_id)
        return "queued"

    def _translation_only_job(self, store: Any, media_id: str) -> None:
        try:
            entry = store.get(media_id)
            if entry is None:
                return
            with telemetry_origin("learner" if entry.library == "personal" else None), system_funding("media_pipeline"):
                def guard() -> None:
                    fresh = store.get(media_id)
                    current = dict(fresh.processing or {}) if fresh is not None else {}
                    if fresh is None or fresh.status == "archived" or current.get("state") in {STATE_QUEUED, STATE_RUNNING, "cancelled"}:
                        raise PipelineStop("cancelled")

                batch_id = str((entry.processing or {}).get("batch_id") or self.new_batch())
                stop: dict[str, Any] = {}
                outcome, counts = self._translate(store, entry, batch_id, entry.library == "personal", stop=stop, resume=True, guard=guard)
                fresh = store.get(media_id) or entry
                outcome = self._defer_translation(store, fresh, outcome, stop)
                fields: dict[str, Any] = {"translation": outcome, "translation_counts": counts}
                if outcome != "deferred":
                    fields["translation_continuation"] = {}
                self._write_processing(store, fresh, **fields)
        except PipelineStop:
            pass  # archived or removed while it ran
        except Exception:  # noqa: BLE001 - the lesson stands; the lines already translated stay
            _logger.exception("translation-only retry crashed for %s", media_id)
            try:
                fresh = store.get(media_id)
                if fresh is not None:
                    self._write_processing(store, fresh, translation=self._short_outcome(fresh), translation_reason="provider_error")
            except Exception:  # noqa: BLE001
                _logger.exception("translation-only retry could not record its own failure for %s", media_id)
        finally:
            with self._guard:
                self._inflight.discard(media_id)

    # -- deferred translation continuation (D-211) ----------------------------------------------------

    def _timer_schedule(self, delay: float, callback: Callable[[], None]) -> None:
        timer = threading.Timer(max(0.0, delay), callback)
        timer.daemon = True
        timer.start()

    @staticmethod
    def _iso(epoch: float) -> str:
        return datetime.fromtimestamp(epoch, UTC).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _epoch(value: Any) -> float:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    def _defer_translation(self, store: Any, entry: MediaLibraryEntry, outcome: str, stop: Mapping[str, Any]) -> str:
        """After a run that ended short on a rate limit: schedule the lines still missing, or say it is over.

        Returns `deferred` when a continuation is scheduled (the item keeps its state: a held item stays held), else the
        outcome unchanged. A restart keeps it: the record is in `processing` and `recover()` arms the timer again."""
        if outcome not in {"partial", "failed"} or stop.get("reason") != "rate_limited":
            return outcome
        previous = (store.get(entry.media_id) or entry).processing.get("translation_continuation") or {}
        now = self._clock()
        attempt = int(previous.get("attempt") or 0) + 1
        deadline = self._epoch(previous.get("deadline")) or now + CONTINUATION_BUDGET_SECONDS
        asked = float(stop.get("retry_after") or 0.0)
        if asked > CONTINUATION_MAX_DELAY and attempt <= CONTINUATION_MAX_ATTEMPTS:
            # Not dropped silently (D-214): the item stays as it is (held, partial), and says why nothing is scheduled.
            _logger.warning("translation continuation not scheduled for %s: the provider asked for %.0f s (limit %.0f s)",
                            entry.media_id, asked, CONTINUATION_MAX_DELAY)
            try:
                self._write_processing(store, entry, translation_reason=REASON_LONG_WAIT, translation_retry_after=round(asked, 1))
            except PipelineStop:
                raise
            except Exception:  # noqa: BLE001 - the reason is a convenience; the lesson stands without it
                _logger.warning("long-wait reason not written for %s", entry.media_id, exc_info=True)
            return outcome
        if asked > CONTINUATION_MAX_DELAY or attempt > CONTINUATION_MAX_ATTEMPTS:
            return outcome
        delay = min(max(asked or CONTINUATION_DEFAULT_DELAY, CONTINUATION_MIN_DELAY), CONTINUATION_MAX_DELAY)
        if now + delay > deadline:
            return outcome
        record = {
            "attempt": attempt, "max_attempts": CONTINUATION_MAX_ATTEMPTS, "next_at": self._iso(now + delay),
            "deadline": self._iso(deadline), "retry_after": round(asked, 1),
        }
        try:
            self._write_processing(store, entry, translation_continuation=record)
        except PipelineStop:
            raise
        except Exception:  # noqa: BLE001 - not recording it means not promising it
            _logger.warning("translation continuation not recorded for %s", entry.media_id, exc_info=True)
            return outcome
        _logger.info("translation continuation %d of %d armed for %s in %.0f s", attempt, CONTINUATION_MAX_ATTEMPTS, entry.media_id, delay)
        self._schedule(delay, lambda: self._continuation_due(store, entry.media_id))
        return "deferred"

    def _rearm_continuation(self, store: Any, entry: MediaLibraryEntry) -> None:
        record = (entry.processing or {}).get("translation_continuation") or {}
        if not record:
            return
        delay = max(0.0, self._epoch(record.get("next_at")) - self._clock())
        self._schedule(delay, lambda: self._continuation_due(store, entry.media_id))

    def _continuation_due(self, store: Any, media_id: str) -> None:
        """The timer fired: hand the continuation to the one pool, unless the item is already being worked."""
        try:
            entry = store.get(media_id)
            processing = dict(entry.processing or {}) if entry is not None else {}
            record = processing.get("translation_continuation")
            if entry is None or not record:
                return
            if self._clock() < self._epoch(record.get("next_at")) - 1.0:
                return  # a stale timer (the record was replaced by a later deferral): the proper one is still armed
            with self._guard:
                if media_id in self._inflight or processing.get("state") in {STATE_QUEUED, STATE_RUNNING}:
                    busy = True
                else:
                    busy = False
                    self._inflight.add(media_id)
            if busy:
                # Something else (a re-run) is on it: look again after one minimum wait.
                self._schedule(CONTINUATION_MIN_DELAY, lambda: self._continuation_due(store, media_id))
                return
            if os.getenv("MEDIA_PIPELINE_INLINE", "").strip() in {"1", "true", "yes"}:
                self._continuation_job(store, media_id)
            else:
                self._pool.submit(self._continuation_job, store, media_id)
        except Exception:  # noqa: BLE001 - a timer thread never dies on it; recover() re-arms after a restart
            _logger.warning("translation continuation not started for %s", media_id, exc_info=True)

    def _continuation_job(self, store: Any, media_id: str) -> None:
        try:
            entry = store.get(media_id)
            if entry is None:
                return
            with telemetry_origin("learner" if entry.library == "personal" else None), system_funding("media_pipeline"):
                self._continue_translation(store, entry)
        except PipelineStop:
            pass  # cancelled or removed while waiting: nothing to continue
        except Exception:  # noqa: BLE001 - the lesson stands; the lines already translated stay
            _logger.exception("translation continuation crashed for %s", media_id)
            try:
                fresh = store.get(media_id)
                if fresh is not None:
                    self._write_processing(store, fresh, translation=self._short_outcome(fresh), translation_reason="provider_error",
                                           translation_continuation={})
            except Exception:  # noqa: BLE001
                _logger.exception("translation continuation could not record its own failure for %s", media_id)
        finally:
            with self._guard:
                self._inflight.discard(media_id)

    @staticmethod
    def _short_outcome(entry: MediaLibraryEntry) -> str:
        counts = (entry.processing or {}).get("translation_counts") or {}
        return "partial" if any(int((item or {}).get("done") or 0) > 0 for item in counts.values()) else "failed"

    def _continue_translation(self, store: Any, entry: MediaLibraryEntry) -> None:
        processing = dict(entry.processing or {})
        record = dict(processing.get("translation_continuation") or {})
        if not record or processing.get("state") in {STATE_QUEUED, STATE_RUNNING}:
            return
        if entry.status == "archived" or processing.get("state") == "cancelled":
            return

        def guard() -> None:
            """Before every provider round: the item is still there, not archived, not re-run, same continuation."""
            fresh = store.get(entry.media_id)
            current = dict(fresh.processing or {}) if fresh is not None else {}
            now_record = current.get("translation_continuation") or {}
            if (fresh is None or fresh.status == "archived" or current.get("state") in {STATE_QUEUED, STATE_RUNNING, "cancelled"}
                    or now_record.get("attempt") != record.get("attempt")):
                raise PipelineStop("cancelled")

        if int(record.get("attempt") or 0) > CONTINUATION_MAX_ATTEMPTS or self._clock() > self._epoch(record.get("deadline")):
            self._write_processing(store, entry, translation=self._short_outcome(entry), translation_continuation={})
            return
        batch_id = str(processing.get("batch_id") or self.new_batch())
        stop: dict[str, Any] = {}
        outcome, counts = self._translate(
            store, entry, batch_id, entry.library == "personal", stop=stop, resume=True,
            max_rounds=CONTINUATION_ROUNDS, max_total_wait=0.0, guard=guard,
        )
        fresh = store.get(entry.media_id) or entry
        outcome = self._defer_translation(store, fresh, outcome, stop)
        fields: dict[str, Any] = {"translation": outcome, "translation_counts": counts}
        if outcome != "deferred":
            fields["translation_continuation"] = {}
        self._write_processing(store, fresh, **fields)

    def _record_translation_reason(self, store: Any, entry: MediaLibraryEntry, reason: str) -> None:
        """Why the translation stopped short, beside `translation_counts`: a stable code, never log prose."""
        try:
            self._write_processing(store, entry, translation_reason=reason)
        except PipelineStop:
            raise
        except Exception:  # noqa: BLE001 - the reason is a convenience; the lesson stands without it
            _logger.warning("translation reason not written for %s", entry.media_id, exc_info=True)

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
