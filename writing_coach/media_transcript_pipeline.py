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
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
import uuid
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from writing_coach import media_quota, media_translation, policies
from writing_coach.media_providers.youtube import REASON_ZH_TRADITIONAL
from writing_coach.ai.audio_telemetry import telemetry_origin
from writing_coach.billing.funding_context import system_funding
from writing_coach.ai.pricing import estimate_token_cost
from writing_coach.book_asset_store import AssetNotFound, BookAssetStore
from writing_coach.media_learning import MediaTranscript, TranscriptSegment
from writing_coach.media_library_store import MediaLibraryEntry
from writing_coach.media_asr_filter import screen_segments
from writing_coach.media_zh_cleanup import clean_asr_cues, normalise_words
from writing_coach.media_segmentation import Cue, first_failure, primary_language, segment_lines, validate_lines
from writing_coach.media_caption_timing import (
    REASON_CAPTION_TIMING,
    TIMING_KEY,
    TIMING_NEXT_START,
    TimingReport,
    caption_timing_report,
    classify_caption_kind,
    clip_to_next_start,
    lesson_caption_facts,
    thresholds as timing_thresholds,
)
from writing_coach.media_spend import KIND_AI, KIND_ASR, SpendCapReached, SpendLedger
from writing_coach.speech_asr import (
    SpeechAsrMalformed,
    SpeechAsrPayloadTooLarge,
    SpeechAsrRequestFailed,
    SpeechAsrResult,
    SpeechAsrSegment,
    SpeechAsrTimedOut,
    SpeechAsrWord,
    ASR_PROMPT_MAX_SECONDS,
    asr_text_has_junk,
    build_asr_prompt,
)

_logger = logging.getLogger(__name__)
CORRECTION_ADMISSION_KEY = "transcript_correction_eligibility"
CORRECTION_ADMISSION_NEW_ADMIN = "new_admin_import"

# Transcript correction (admin ASR/caption repair): bounded batches, per-cue acceptance, bounded rate-limit handling.
CORRECTION_BATCH_CUES = 24
CORRECTION_BATCH_CHARACTERS = 6_000
# The model's answer is JSON per cue (`{"index":N,"text":"...","reason":"..."}`): a fixed overhead plus the text itself. Measured
# on the live trial (2026-10-17, 24 Chinese cues, 630 text bytes -> 869 completion tokens) and rounded up, so a batch that fits
# the provider's output-token allowance by this estimate is not cut off mid-answer (`finish_reason: length` is unusable JSON).
CORRECTION_OUTPUT_TOKENS_PER_CUE = 28
CORRECTION_OUTPUT_TOKENS_PER_BYTE = 0.6


def estimate_correction_output_tokens(cues: Iterable[Cue]) -> int:
    """About how many tokens the provider writes to answer these cues."""
    total = 0
    for cue in cues:
        total += CORRECTION_OUTPUT_TOKENS_PER_CUE + math.ceil(len(cue.text.encode("utf-8")) * CORRECTION_OUTPUT_TOKENS_PER_BYTE)
    return total


def fit_correction_batch(batch: list[tuple[int, Cue]], ceiling: int | None) -> list[tuple[int, Cue]]:
    """The longest leading part of `batch` whose answer fits `ceiling` output tokens (all when no ceiling is known).

    A first cue that alone does not fit is still returned as a batch of one: `correction_cue_fits` is how the caller finds
    out and keeps such a cue raw instead of sending a request known to be cut off."""
    if not ceiling or len(batch) <= 1:
        return batch
    used = 0
    for count, (_, cue) in enumerate(batch):
        used += estimate_correction_output_tokens([cue])
        if used > ceiling:
            return batch[:max(1, count)]
    return batch


def correction_cue_fits(cue: Cue, ceiling: int | None) -> bool:
    """Whether the answer for this one cue is estimated to fit `ceiling` output tokens (always when none is known)."""
    return not ceiling or estimate_correction_output_tokens([cue]) <= ceiling


def correction_ceiling(corrector: Any) -> int | None:
    """What one correction request can really carry, from the provider: its per-request cap combined with its learned
    output allowance (`correction_output_ceiling`), else the allowance alone (`batch_output_ceiling`), else None. An
    unreadable answer means no ceiling is known, never a failure."""
    for name in ("correction_output_ceiling", "batch_output_ceiling"):
        read = getattr(corrector, name, None)
        if not callable(read):
            continue
        try:
            value = read()
        except Exception:  # noqa: BLE001 - an unknown allowance only means the batch is not narrowed
            continue
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return None
# One retry per batch, only for a rate limit whose named wait fits one cap and the shared allowance (the translation
# run's own total, TRANSLATION_MAX_TOTAL_WAIT). 90 s covers the 62 s the output-token window asks (D-218).
CORRECTION_ATTEMPTS = 2
CORRECTION_MAX_WAIT = 90.0
CORRECTION_PROVIDER_REASONS = frozenset({"rate_limited", "provider_auth", "provider_timeout", "provider_error",
                                         "malformed_result", "request_too_large", "not_configured"})
# Chinese per-cue edit allowance (changed Han characters, Levenshtein over the Han characters only): a quarter of the cue's
# Han characters, at least 2 and at most 4, always leaving one original character of a cue longer than one. It admits the
# one- and two-character homophone fixes ASR needs (渡舰->渡江, 船一正->船身, 舰->剑) and refuses a rewrite of a cue.
ZH_EDIT_FLOOR = 2
ZH_EDIT_CAP = 4
ZH_EDIT_SHARE = 0.25
# A correction that was attempted and did not finish as `applied` never blocks the item: it is translated on the best
# available text. It does stop AUTOMATIC publication, because a person cleared the rights of the corrected transcript, not
# of the raw one (D-111: auto-publish only when every check passed). The item is held with this reason and a person
# publishes it, or retries it, knowing the text may still carry recognition errors. `unavailable` (an unsupported language,
# or no corrector configured on this deployment) is not an attempt that failed - nothing was tried - so it does not hold.
CORRECTION_HOLD_STATES = frozenset({"partial", "failed"})
REASON_CORRECTION_INCOMPLETE = "transcript_correction_incomplete"
# The hold must survive a retry or a reprocess: a re-run resets the correction state and (as a retry consumes eligibility)
# would otherwise meet a cleared item with no correction state at all and publish the raw text. This durable marker is set
# whenever a shared item finished with its correction incomplete, and cleared only when a run ends with the correction
# `applied` or when a person publishes the item by hand (their decision, after checking the transcript).
CORRECTION_UNRESOLVED_KEY = "transcript_correction_unresolved"
_HAN_CHARACTER = re.compile(r"[㐀-䶿一-鿿豈-﫿]")

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

# Rights decision 2026-10-19 (D-244): Orena never downloads a YouTube video's audio to run speech recognition. A YouTube
# item is transcribed from the captions the provider offers or not at all, whatever its transcript policy says, so
# `captions_or_asr` listens to the audio only for a file the learner or admin uploaded, or another source whose rights
# allow it. The item stops with this reason, before any download, recognition or spend; the caption cause is the detail.
REASON_YOUTUBE_NO_CAPTIONS = "youtube_no_channel_captions"

# Where the stored transcript's text came from, kept beside `transcript_origin` (D-244): the channel's own captions (a
# track a person made), the provider's machine-generated captions, a caption track whose kind the provider did not say,
# or Orena's speech recognition of audio it was allowed to use.
PROVENANCE_CHANNEL_CAPTIONS = "channel_captions"
PROVENANCE_MACHINE_CAPTIONS = "machine_captions"
PROVENANCE_CAPTIONS_UNKNOWN = "captions_unknown_kind"
PROVENANCE_ORENA_ASR = "orena_asr"


def transcript_provenance(origin: str, caption_kind: str) -> str:
    """The provenance of a transcript from its origin and, for captions, the track's kind (`manual`, `auto`, other)."""
    if origin == ORIGIN_ASR:
        return PROVENANCE_ORENA_ASR
    if origin != ORIGIN_CAPTION:
        return ""
    kind = str(caption_kind or "").casefold()
    if kind == "manual":
        return PROVENANCE_CHANNEL_CAPTIONS
    if kind == "auto":
        return PROVENANCE_MACHINE_CAPTIONS
    return PROVENANCE_CAPTIONS_UNKNOWN

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
# The correction step draws on the same total allowance of waiting as one translation run.
CORRECTION_MAX_TOTAL_WAIT = TRANSLATION_MAX_TOTAL_WAIT
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
# How long one continuation may hold the worker waiting inside the provider for an output-token window to clear (D-218). A
# provider with an output-tokens-per-minute limit admits a few lines a minute; the schedule alone would make a long item
# take one window per attempt and run out of attempts. Bounded like the first run's waits (TRANSLATION_MAX_TOTAL_WAIT).
CONTINUATION_PACING_SECONDS = 150.0


# The stable reason codes an item can be held or failed with, each with the English sentence stored beside it
# (`processing["message"]`) for anything that reads the record directly. The console words each code itself, in the
# operator's language (`impErr_<code>`); a code not listed here has no stored message, never a made-up one.
REASON_MESSAGES: dict[str, str] = {
    "rights_unknown": "The transcript is ready; rights are unknown, so it is held until a person confirms them.",
    "transcript_correction_incomplete": "Rights are cleared, but the automatic transcript correction did not finish, so the item is held instead of publishing uncorrected text.",
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
    "zh_traditional_not_accepted": "The only Chinese captions offered are Traditional; only Simplified is accepted for now. Nothing was translated.",
    "caption_quota": "Today's limit of caption requests to the caption provider was reached; none was sent.",
    REASON_CAPTION_TIMING: "The caption timing does not follow the speech, so the item is held for timing review and not published.",
    REASON_YOUTUBE_NO_CAPTIONS: "YouTube video without channel captions: Orena does not download YouTube audio (rights decision 2026-10-19).",
    "spend_cap_day": "The daily processing spend limit was reached.",
    "spend_cap_batch_asr": "The speech recognition spend limit for this batch was reached.",
    "spend_cap_batch_ai": "The AI spend limit for this batch was reached.",
}


def reason_message(code: str) -> str:
    return REASON_MESSAGES.get(str(code or ""), "")


def caption_check_detail(checks: Any, captions: int, lines: int) -> str:
    """The first failing quality check of fetched captions, by its stable id and its own count, and how many captions and
    lines there were: `segments: 242 lines; 242 captions, 242 lines`. Language-neutral on purpose (ids and numbers), so the
    admin shows it beside the translated reason without new copy (D-218)."""
    failed = next((check for check in checks if not check.get("pass")), None)
    if failed is None:
        return ""
    return f"{failed.get('id')}: {failed.get('detail')}; {captions} captions, {lines} lines"[:200]


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


def _screen_fields(screen: dict[str, Any]) -> dict[str, int]:
    """What the ASR screen removed or doubted, recorded so a reviewer sees it (empty for a caption transcript)."""
    if not screen or "filtered" not in screen or "flagged" not in screen:
        return {}
    return {"asr_filtered": int(screen["filtered"]), "asr_flagged": int(screen["flagged"])}


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


CARRY_WINDOW = 8


def carry_segment_ids(previous_payload: Mapping[str, Any] | None, transcript: MediaTranscript) -> tuple[MediaTranscript, int]:
    """Keep a line's identity when a re-run only moved it in time (P0 2026-10-20 re-time sweep).

    A segment id hashes its start and end, so re-timing an item would give every line a new id and detach what points at
    the old one: listening and shadowing progress, speaking attempts, saved words and notes, the learner's place, the
    meaning cache. A new line takes the id of the old line with the same text, matched in order (each old id once, within
    a short window ahead of the last match), so references follow the line to its corrected time. A line whose text
    changed keeps its new id, exactly as before. Returns (transcript, how many ids were carried)."""
    transcript_payload = (previous_payload or {}).get("transcript") if isinstance(previous_payload, Mapping) else None
    rows = transcript_payload.get("segments") if isinstance(transcript_payload, Mapping) else None
    old = [(str(row.get("segment_id") or ""), _normal_text(str(row.get("original_text") or "")))
           for row in (rows or []) if isinstance(row, Mapping) and row.get("segment_id")]
    if not old:
        return transcript, 0
    carried: list[TranscriptSegment] = []
    pointer = carried_count = 0
    for segment in transcript.segments:
        key = _normal_text(segment.original_text)
        match = next((index for index in range(pointer, min(len(old), pointer + CARRY_WINDOW)) if old[index][1] == key), None)
        if match is None:
            carried.append(segment)
            continue
        pointer = match + 1
        carried_count += int(old[match][0] != segment.segment_id)
        carried.append(replace(segment, segment_id=old[match][0]))
    if len({segment.segment_id for segment in carried}) != len(carried):
        return transcript, 0   # a carried id met a new one: keep the new ids rather than merge two lines
    try:
        return MediaTranscript(asset_id=transcript.asset_id, source_language=transcript.source_language,
                               segments=tuple(carried)), carried_count
    except Exception:  # noqa: BLE001 - the contract refused the carried ids; the new ones stand
        return transcript, 0


def _normal_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split()).casefold()


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


def _unicode_lexemes(text: str) -> list[str]:
    """Normalize lexical tokens across scripts, retaining combining marks and numbers."""
    tokens: list[str] = []
    current: list[str] = []
    for char in unicodedata.normalize("NFC", text):
        category = unicodedata.category(char)
        if category[0] in {"L", "N"} or (category[0] == "M" and current):
            current.append(char)
        elif char in {"'", "\u2019"} and current:
            current.append("'")
        else:
            if current:
                tokens.append("".join(current).casefold())
                current = []
    if current:
        tokens.append("".join(current).casefold())
    return tokens


def _non_han_lexemes(text: str) -> list[str]:
    """The words and numbers of a Chinese cue that are not Han characters (VOA, GPT-5, 2025): a Han character is a
    separator here, so 这是VOA新闻 reads as ["voa"]. These are entities and figures, never recognition errors to repair."""
    return _unicode_lexemes(_HAN_CHARACTER.sub(" ", text))


def _han_edit_distance(before: str, after: str) -> int:
    a, b = _HAN_CHARACTER.findall(before), _HAN_CHARACTER.findall(after)
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            row.append(min(previous[j] + 1, row[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = row
    return previous[-1]


def reject_cue_edit(language: str, before: str, after: str) -> str:
    """Why one proposed cue text is refused, as a stable code, or "" when it may replace `before`.

    The rule is per cue, so one bad proposal never costs the valid ones. Every cue: non-empty and within twice its length.
    English: the lexemes (words and numbers) must be unchanged. Chinese: the changed Han characters must stay within the
    ZH_EDIT_* allowance for the cue's length, and every non-Han word or number (VOA, GPT-5, 2025) must be unchanged;
    punctuation stays free."""
    if not after.strip():
        return "empty_cue"
    if len(after) > max(200, 2 * len(before) + 24):
        return "malformed_result"
    if language == "en":
        return "" if _unicode_lexemes(before) == _unicode_lexemes(after) else "lexemes_changed"
    if _non_han_lexemes(before) != _non_han_lexemes(after):
        return "lexemes_changed"
    han = len(_HAN_CHARACTER.findall(before))
    allowed = max(1, min(han - 1, max(ZH_EDIT_FLOOR, min(ZH_EDIT_CAP, math.ceil(han * ZH_EDIT_SHARE)))))
    return "" if _han_edit_distance(before, after) <= allowed else "edit_ratio_exceeded"



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


def caption_timing_gate(entry: MediaLibraryEntry, lines: list[Cue] | None = None) -> tuple[bool, str, TimingReport | None]:
    """The caption-timing gate for a stored entry (P0 2026-10-20): (passes, detail, report).

    Applies to a transcript made from provider captions; any other origin passes (`None` report). Run before anything is
    published - the pipeline's automatic publication, the operator's Publish, a content-pack import - so a mistimed
    transcript is held for timing review (`caption_timing`) instead of reaching a learner. A track whose kind the
    provider did not say is classified from its markers (`>>`, `[music]`)."""
    applies, kind, retimed = lesson_caption_facts(entry)
    if not applies:
        return True, "", None
    if lines is None:
        lines = lines_from_payload((entry.lesson or {}).get("payload") if entry.lesson else None)
    report = caption_timing_report(lines, language=entry.language, caption_kind=classify_caption_kind(kind, lines),
                                   retimed=retimed, limits=timing_thresholds())
    return report.passed, ("" if report.passed else report.detail()[:200]), report


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
        corrector: Any = None,
        fallback_corrector: Any = None,
    ) -> None:
        self._ledger = ledger
        self._asr = asr
        self._ingestion = ingestion
        self._admin_ingestion = admin_ingestion   # an operator's (shared) item may take captions from Supadata (D-215)
        self._youtube_audio = youtube_audio
        self._meanings = meanings
        self._english_reading = english_reading
        self._corrector = corrector
        # D-224 (PROPOSED): what a correction batch Groq cannot take is sent to (the platform router), or None.
        self._fallback_corrector = fallback_corrector
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
        entry = store.get(media_id) or entry
        if entry.library == "shared" and (entry.processing or {}).get(CORRECTION_UNRESOLVED_KEY):
            # Held because its correction did not finish (never published): the correction runs again on this retry, so
            # the item can finish `applied`. Whatever happens, it cannot auto-publish without that (see `_run`).
            self._grant_correction_admission(store, media_id)
        else:
            self._clear_correction_admission(store, media_id)
        entry = store.get(media_id) or entry
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
            # A re-run that failed (no captions this time, a quota, a provider error) puts the item back exactly as it
            # was, published or not, and says why; only new captions that fail the timing gate hold an item (in `_run`).
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

    @staticmethod
    def _grant_correction_admission(store: Any, media_id: str) -> None:
        def change(fresh: MediaLibraryEntry) -> MediaLibraryEntry:
            current = dict(fresh.processing or {})
            current[CORRECTION_ADMISSION_KEY] = CORRECTION_ADMISSION_NEW_ADMIN
            return replace(fresh, processing=current)
        try:
            store.update_if_present(media_id, change)
        except Exception:  # noqa: BLE001 - without it the retry runs uncorrected and the hold marker still stops publication
            _logger.warning("transcript correction admission not granted for %s", media_id, exc_info=True)

    @staticmethod
    def _clear_correction_admission(store: Any, media_id: str) -> None:
        def change(fresh: MediaLibraryEntry) -> MediaLibraryEntry:
            current = dict(fresh.processing or {})
            if CORRECTION_ADMISSION_KEY not in current:
                return fresh
            current.pop(CORRECTION_ADMISSION_KEY, None)
            previous = current.get("previous")
            if isinstance(previous, Mapping):
                previous = dict(previous)
                previous.pop(CORRECTION_ADMISSION_KEY, None)
                current["previous"] = previous
            return replace(fresh, processing=current)
        try:
            store.update_if_present(media_id, change)
        except Exception:  # noqa: BLE001 - failure must not turn a retry into correction admission
            _logger.warning("transcript correction admission not cleared for %s", media_id, exc_info=True)

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
                self._clear_correction_admission(store, entry.media_id)
                self._settle_quota(store, entry.media_id, media_quota.hold_of(entry), final=entry)
                self._rearm_continuation(store, entry)
                continue
            if int(processing.get("attempts") or 0) >= MAX_ATTEMPTS:
                if self._restore_previous(store, entry.media_id, "pipeline_interrupted"):
                    self._clear_correction_admission(store, entry.media_id)
                    self._settle_quota(store, entry.media_id, media_quota.hold_of(entry))
                    continue
                self._write_processing(store, entry, state=STATE_FAILED, stage=processing.get("stage") or STAGE_FETCH,
                                       reason="pipeline_interrupted", detail="Processing was interrupted too many times.",
                                       status="review")
                self._clear_correction_admission(store, entry.media_id)
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
            if target_status == "published" and fresh.library == "shared":
                # The last step before a learner sees it: the caption-timing gate, whatever path got here.
                timing_ok, timing_detail, _report = caption_timing_gate(fresh)
                if not timing_ok:
                    target_status = "review"
                    processing.update(state=STATE_HELD, reason=REASON_CAPTION_TIMING, detail=timing_detail, auto_published=False)
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
                                           transcript_correction_state="", transcript_correction_detail="", transcript_corrections=[], transcript_correction_rejected=[],
                                           caption_kind="", caption_provider="", caption_language="", caption_fallback="", caption_fallback_detail="", reprocess_reason="", reprocess_detail="", reprocess_message="",
                                           **{TIMING_KEY: ""})
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
                self._clear_correction_admission(store, media_id)
                return  # the item had a good transcript; the new one is not kept over it
            # A transcript was made and it is not usable. Keep what was made so an operator can see it; do not publish.
            entry = self._store_lesson(store, entry, lines, origin, duration, status="review", words=words)
            self._write_processing(store, entry, state=STATE_FAILED, stage=STAGE_SEGMENT, reason=reason,
                                   detail="", checks=public_checks, origin=origin, cost_usd=round(cost, 6), asr_seconds=round(asr_seconds, 1),
                                   **_screen_fields(screen))
            self._clear_correction_admission(store, media_id)
            return
        entry = self._store_lesson(store, entry, lines, origin, duration, status="processing", words=words)
        if not personal:
            timing_ok, timing_detail, _report = caption_timing_gate(entry)
            if not timing_ok:
                # Caption timing that does not follow the speech is never published (P0 2026-10-20): held for timing review,
                # before any translation is paid for. The previous transcript is not restored over it - it was cut by the
                # same rule or an older one, and a person decides from here (reprocess, or correct the cues).
                self._clear_previous(store, media_id)
                entry = store.get(media_id) or entry
                self._write_processing(store, entry, state=STATE_HELD, stage=STAGE_SEGMENT, reason=REASON_CAPTION_TIMING,
                                       detail=timing_detail, checks=public_checks, origin=origin, cost_usd=round(cost, 6),
                                       asr_seconds=round(asr_seconds, 1), auto_published=False, previous={},
                                       status="review", **_screen_fields(screen))
                self._clear_correction_admission(store, media_id)
                return
        stop: dict[str, Any] = {}
        translation, translation_counts = self._translate(store, entry, batch_id, personal, stop=stop)
        translation = self._defer_translation(store, entry, translation, stop)
        entry = store.get(media_id) or entry
        rights = str(entry.source.get("rights") or RIGHTS_UNKNOWN)
        common = dict(previous={}, checks=public_checks, origin=origin, cost_usd=round(cost, 6), asr_seconds=round(asr_seconds, 1),
                      translation=translation, translation_counts=translation_counts, rights=rights, **_screen_fields(screen))
        # Only an eligible shared item has a correction state (a learner's own import never does). Anything but `applied`
        # means the cleared rights do not yet cover the text a learner would read, so it is not published by itself. An item
        # already held for an unfinished correction stays held until a run ends `applied`: a retry that did not correct
        # (no state, or `unavailable`) must not turn the raw text into an automatic publication.
        correction_state = str((entry.processing or {}).get("transcript_correction_state") or "")
        owed = bool((entry.processing or {}).get(CORRECTION_UNRESOLVED_KEY)) and not personal
        correction_incomplete = correction_state in CORRECTION_HOLD_STATES or (owed and correction_state != "applied")
        common[CORRECTION_UNRESOLVED_KEY] = bool(correction_incomplete and not personal)
        if not personal and rights == RIGHTS_CLEARED and not correction_incomplete:
            # D-240: an item that publishes by itself has a thumbnail. A provider-hosted or extracted one stands; an
            # audio file with no artwork gets Orena's typographic cover (source 3), made here once.
            from writing_coach.thumbnails import has_media_thumbnail, media_entry_with_cover

            if assets is not None and not has_media_thumbnail(entry.thumbnail):
                entry = media_entry_with_cover(entry, assets)
        if personal or (rights == RIGHTS_CLEARED and not correction_incomplete):
            # Readiness is when source artifacts are made, once (D-121); the model clip Compare measures is one (D-140).
            # A skip (a YouTube item, D-244) is recorded for the admin outcome; it is not an error and moves no state.
            common["model_clips_skipped"] = self._prepare_model_clips(assets, entry) or ""
        if personal:
            self._write_processing(store, entry, state=STATE_READY, stage=STAGE_READY, reason="", detail="", auto_published=False, **common, status="published")
        elif rights == RIGHTS_CLEARED and correction_incomplete:
            self._write_processing(store, entry, state=STATE_HELD, stage=STAGE_READY, reason=REASON_CORRECTION_INCOMPLETE, detail=correction_state,
                                   auto_published=False, **common, status="review")
        elif rights == RIGHTS_CLEARED:
            self._write_processing(store, entry, state=STATE_READY, stage=STAGE_READY, reason="", detail="", auto_published=True, **common, status="published")
        else:
            self._write_processing(store, entry, state=STATE_HELD, stage=STAGE_READY, reason="rights_unknown", detail="", auto_published=False, **common, status="review")
        self._clear_correction_admission(store, media_id)

    def _prepare_model_clips(self, assets: BookAssetStore, entry: MediaLibraryEntry) -> str | None:
        """Cut each speakable line's model clip once, from the source this item was admitted from.

        Idempotent (a stored clip is never cut again), bounded, provider-free, and never able to fail
        readiness: a lesson without clips is complete, and Compare says its model plot is unavailable.
        A YouTube item is never cut, because Orena does not download YouTube audio (D-244, amended
        2026-10-20): the skip reason is returned (and logged), and nothing is downloaded.
        """
        from writing_coach import model_clips, policies

        if not policies.value("media.model_clips_enabled"):
            return None
        if model_clips.is_youtube_provider(getattr(entry, "provider", "")):
            _logger.info("model clips for %s: skipped, %s", entry.media_id, model_clips.SKIP_YOUTUBE_NOTE)
            return model_clips.SKIP_YOUTUBE_NO_AUDIO_DOWNLOAD
        try:
            from writing_coach.speaking_library import entry_clip_lines

            lesson = dict(entry.lesson or {})
            admitted = replace(entry, status="published", lesson={**lesson, "status": "PUBLISHED"})
            pending = model_clips.missing_lines(assets, entry_clip_lines(admitted))
            if not pending:
                return None
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
        return None

    def _hold_failed(self, store: Any, media_id: str, stop: PipelineStop) -> None:
        entry = store.get(media_id)
        if entry is None:
            return
        if entry.status == "archived" or stop.code == "cancelled":
            self._clear_previous(store, media_id)
            self._clear_correction_admission(store, media_id)
            return
        if self._restore_previous(store, media_id, stop.code, stop.detail):
            self._clear_correction_admission(store, media_id)
            return
        self._write_processing(store, entry, state=STATE_FAILED, reason=stop.code, detail=stop.detail, status="review", previous={})
        self._clear_correction_admission(store, media_id)

    def _store_lesson(self, store: Any, entry: MediaLibraryEntry, lines: list[Cue], origin: str, duration: int, *, status: str, words: list[SpeechAsrWord] | None = None) -> MediaLibraryEntry:
        transcript = build_transcript(entry.media_id, entry.language, lines)
        # A re-run keeps each unchanged line's identity, so what points at it stays attached after a re-time.
        transcript, _carried = carry_segment_ids((entry.lesson or {}).get("payload") if entry.lesson else None, transcript)
        payload = lesson_payload(entry, transcript, origin, duration, words=words, english_reading=self._english_reading)
        # Channel captions, machine captions or Orena's recognition: told apart wherever the origin is (D-244).
        provenance = transcript_provenance(origin, str((entry.processing or {}).get("caption_kind") or ""))
        payload["transcript_provenance"] = provenance
        if origin == ORIGIN_CAPTION:
            # The kind and the re-timing travel with the lines (a content pack carries the lesson, not the processing record),
            # so the caption-timing gate can tell a re-timed automatic track from one cut before the fix.
            processing_now = entry.processing or {}
            payload["caption_kind"] = str(processing_now.get("caption_kind") or "")
            payload[TIMING_KEY] = str(processing_now.get(TIMING_KEY) or "")
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
            processing = ({**dict(fresh.processing or {}), "origin": origin, "transcript_provenance": provenance}
                          if fresh.processing is not None else fresh.processing)
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
                # The kind is read from the cues as the provider gave them (a rolling auto track overlaps), then every cue
                # ends no later than the next one starts: a cue's own end is when it leaves the screen (D-020, P0 2026-10-20).
                kind = classify_caption_kind(kind, cues)
                cues, _clipped = clip_to_next_start(cues)
                lines = segment_lines(cues, language)
                duration = int(entry.duration_ms or 0)
                checks = validate_lines(lines, language=language, duration_ms=duration)
                if not first_failure(checks):
                    self._write_processing(store, entry, caption_kind=kind, caption_provider=provider,
                                           caption_language=caption_language, caption_fallback="", caption_fallback_detail="",
                                           **{TIMING_KEY: TIMING_NEXT_START})
                    lines, correction = self._correct_transcript(store, entry, batch_id, lines, origin=ORIGIN_CAPTION)
                    return lines, ORIGIN_CAPTION, 0.0, 0.0, "", [], correction
                # Captions that are not good enough fall through to the audio (D-111 item 3).
                fallback = "captions_unusable"
                # Which check refused them, with its own count, so an operator is not left to guess (D-218).
                captions_error = caption_check_detail(checks, len(cues), len(lines))
            elif captions_error:
                fallback = captions_error if captions_error in {"caption_quota", REASON_ZH_TRADITIONAL} else "captions_unavailable"
            if captions_error == REASON_ZH_TRADITIONAL:
                # Owner decision 2026-10-15: only Simplified Chinese is accepted. The track is refused whatever the
                # transcript policy says: no audio is downloaded, no recognition runs, nothing is translated or spent (D-218).
                raise PipelineStop(REASON_ZH_TRADITIONAL, "")
            if self._keeps_captions(entry):
                # The stored transcript is the provider's own captions and they cannot be had now: it stays, and the
                # audio is not listened to in its place (D-213). The item is restored by the caller.
                raise PipelineStop(fallback or "captions_unavailable", captions_error)
            if entry.source.get(SOURCE_TRANSCRIPT_POLICY) == POLICY_CAPTIONS_ONLY:
                # The operator asked for captions or nothing (D-214): no audio is downloaded, no recognition runs, nothing
                # is spent. The item fails with the stable reason and can be re-run once the provider answers.
                raise PipelineStop(fallback or "captions_unavailable", captions_error)
            # Rights decision 2026-10-19 (D-244): the audio of a YouTube video is never downloaded for recognition. A caption
            # fetch the provider refused this time (or the daily caption cap) keeps its own retryable reason; a video with no
            # caption track, or one too poor to use, stops with the rights reason, the caption cause as its detail.
            if captions_error and fallback != "captions_unusable":
                raise PipelineStop(fallback or "captions_unavailable", captions_error)
            raise PipelineStop(REASON_YOUTUBE_NO_CAPTIONS, captions_error if fallback == "captions_unusable" else "no_caption_track")
        self._write_processing(store, entry, state=STATE_RUNNING, stage=STAGE_TRANSCRIBE, caption_kind="", caption_provider="",
                               caption_language="", caption_fallback=fallback,
                               caption_fallback_detail=captions_error if fallback == "captions_unusable" else "")
        # Only a source with no caption track reaches here (an upload, or a non-YouTube source whose rights allow listening);
        # `captions_blocked` (captions refused and the YouTube audio refused too) is no longer produced since D-244.
        raw, words, detected, cost, seconds, screen = self._speech(store, assets, entry, batch_id)
        # Chinese recognition output is repaired (no spaces between Hanzi, sentence marks, no leading silence) before it is cut.
        raw = clean_asr_cues(raw, words, language or detected)
        words = normalise_words(words, language or detected)  # the same script as the lines, so taps stay aligned
        lines = segment_lines(raw, language)
        lines, correction = self._correct_transcript(store, entry, batch_id, lines, origin=ORIGIN_ASR)
        return lines, ORIGIN_ASR, cost, seconds, detected, words, {**screen, **correction}

    @staticmethod
    def _is_correction_eligible(entry: MediaLibraryEntry) -> bool:
        """Only a never-published, shared admin import may be corrected automatically."""
        if entry.library != "shared" or str((entry.source or {}).get("imported_by") or "").casefold() == "learner":
            return False
        processing = entry.processing if isinstance(entry.processing, Mapping) else {}
        if processing.get(CORRECTION_ADMISSION_KEY) != CORRECTION_ADMISSION_NEW_ADMIN:
            return False
        previous = processing.get("previous")
        if isinstance(previous, Mapping) and previous:
            status = str(previous.get("_status") or previous.get("status") or "").casefold()
            lesson = previous.get("lesson") if isinstance(previous.get("lesson"), Mapping) else {}
            if status in {"published", "ready"} or str(lesson.get("status") or "").casefold() == "published":
                return False
        # lesson.status is projected as PUBLISHED even for newly acquired media. Durable admission evidence,
        # created before the first upsert, distinguishes those from legacy and previously admitted records.
        return True

    def _correct_transcript(
        self, store: Any, entry: MediaLibraryEntry, batch_id: str, lines: list[Cue], *, origin: str
    ) -> tuple[list[Cue], dict[str, Any]]:
        """Correct an eligible admin transcript in bounded, metered batches, one cue at a time.

        Acceptance is per cue: every valid repair is kept, an offending cue keeps its raw text and is recorded with a
        reason code (`transcript_correction_rejected`). A later batch that fails keeps the batches already accepted.
        The outcome (`applied`, `partial`, `failed`, `unavailable` + `transcript_correction_detail`) is recorded and
        never stops the item: the pipeline goes on to translation on the best available text."""
        language = primary_language(entry.language)
        if language == "zh" and origin != ORIGIN_ASR:
            return lines, {}
        if not self._is_correction_eligible(entry):
            return lines, {}
        from writing_coach.media_transcript_quality import repair_english_caption_text

        if language not in {"en", "zh"}:
            return lines, self._correction_outcome(store, entry, "unavailable", "unsupported_language")
        # Deterministic baseline (English only): speaker marks and sound tags out. A cue that is nothing but noise is
        # dropped, as the canonical caption cleaning drops it; it never aborts the repair. Chinese text is never stripped.
        baseline: list[tuple[int, Cue]] = []
        dropped: list[int] = []
        for index, line in enumerate(lines):
            text = repair_english_caption_text(line.text) if language == "en" else line.text
            if text.strip():
                baseline.append((index, Cue(line.start_ms, line.end_ms, text)))
            else:
                dropped.append(index)
        if not baseline:
            return lines, self._correction_outcome(store, entry, "failed", "empty_cue")
        accepted: dict[int, str] = {index: cue.text for index, cue in baseline}
        rejected: list[dict[str, Any]] = []
        reasons: dict[int, str] = {}
        providers: list[str] = []
        models: list[str] = []
        notes: dict[str, str] = {}
        correct = getattr(self._corrector, "correct", None)
        primary_ready = callable(correct) and getattr(self._corrector, "configured", True) is not False
        if not primary_ready and self._fallback_ready():
            # Groq has no credential here: every batch goes straight to the router (the loop's first refusal).
            correct, primary_ready = self._without_primary, True
        if not primary_ready:
            state, detail = "unavailable", "corrector_unconfigured"
        else:
            state, detail = self._run_correction_batches(
                entry, batch_id, language, baseline, correct, accepted, reasons, rejected, providers, models, notes)
        return self._finish_correction(store, entry, lines, baseline, dropped, accepted, reasons, rejected,
                                       providers, models, state, detail, notes)

    def _run_correction_batches(
        self, entry: MediaLibraryEntry, batch_id: str, language: str, baseline: list[tuple[int, Cue]], correct: Any,
        accepted: dict[int, str], reasons: dict[int, str], rejected: list[dict[str, Any]],
        providers: list[str], models: list[str], notes: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        """Run the model over `baseline` (filling the accepted/reasons/rejected collectors); returns (state, detail)."""
        batches: list[list[tuple[int, Cue]]] = []
        current: list[tuple[int, Cue]] = []
        characters = 0
        for item in baseline:
            size = len(item[1].text)
            if size > CORRECTION_BATCH_CHARACTERS:
                return "failed", "request_too_large"
            if current and (len(current) >= CORRECTION_BATCH_CUES or characters + size > CORRECTION_BATCH_CHARACTERS):
                batches.append(current)
                current, characters = [], 0
            current.append(item)
            characters += size
        if current:
            batches.append(current)
        description = str((entry.source or {}).get("description") or "")[:1000]
        model = str(getattr(self._corrector, "model_version", "") or getattr(self._corrector, "model", "") or "")
        # One allowance of seconds, shared by every batch: what the provider may wait inside a call for its output-token
        # window (D-218) and what a named rate-limit wait between attempts draws on. Spent, a batch is not retried.
        pace = media_translation.PacingBudget(CORRECTION_MAX_TOTAL_WAIT)
        succeeded = 0
        failure = ""
        queue = deque(batches)
        while queue:
            batch = queue.popleft()
            batch_cues = tuple(cue for _, cue in batch)
            result: Any = None
            skipped = False
            for attempt in range(CORRECTION_ATTEMPTS):
                # What one request can really carry is the provider's per-request completion cap (always) combined with the
                # output allowance it learns from its first refusal (later), so the batch is fitted to it at every attempt,
                # the retry after a rate limit included: an answer that does not fit is cut off mid-JSON and is unusable (the
                # live trial's `malformed_result`). The cues that do not fit go back to the front of the queue.
                ceiling = correction_ceiling(self._corrector)
                fitted = fit_correction_batch(batch, ceiling)
                if len(fitted) < len(batch):
                    queue.appendleft(batch[len(fitted):])
                    batch = fitted
                    batch_cues = tuple(cue for _, cue in batch)
                if len(batch) == 1 and not correction_cue_fits(batch[0][1], ceiling):
                    # One cue whose answer alone cannot fit a request: it is not sent (the answer would be cut off). It keeps
                    # its raw text and is recorded, like any other cue the correction could not take.
                    index, cue = batch[0]
                    rejected.append({"index": index, "start_ms": cue.start_ms, "code": "cue_too_large",
                                     "before": cue.text[:1000], "proposed": ""})
                    skipped = True
                    break
                context_bytes = len(entry.title.encode("utf-8")) + len(description.encode("utf-8"))
                tokens = max(512, min(8192, sum(len(cue.text.encode("utf-8")) for cue in batch_cues) + context_bytes + 1000))
                try:
                    self._ledger.check(KIND_AI, batch_id, self._ai_cost(
                        model, {"prompt_tokens": tokens, "completion_tokens": tokens}, self._target_provider(self._corrector)))
                except SpendCapReached:
                    failure = "spend_cap"
                    break
                except Exception:  # noqa: BLE001
                    _logger.warning("transcript correction could not be prepared for %s", entry.media_id, exc_info=True)
                    failure = "correction_unavailable"
                    break
                usage: list[tuple[str, Any, str]] = []
                retry_after = 0.0
                # One call may wait inside the provider (for the output-token window) at most CORRECTION_MAX_WAIT, and what it
                # spends there comes off the shared total: the provider only knows the budget it is handed, so the per-wait cap
                # is the budget of the call, not the whole allowance.
                call_pace = media_translation.PacingBudget(min(CORRECTION_MAX_WAIT, pace.remaining))
                offered = call_pace.remaining
                try:
                    with media_translation.translation_pacing(call_pace):
                        if self._translation_sink is not None:
                            with self._translation_sink(self._usage_collector(usage)):
                                result = correct(language=language, cues=batch_cues, title=entry.title, description=description)
                        else:
                            result = correct(language=language, cues=batch_cues, title=entry.title, description=description)
                    # A corrector that returns nothing and raises nothing has still not answered: a stable failure, never a
                    # silent skip of the batch.
                    failure = "" if result is not None else "malformed_result"
                except Exception as exc:  # noqa: BLE001 - the provider's stable reason is kept, never its message
                    code = str(getattr(exc, "reason", "") or "")
                    failure = code if code in CORRECTION_PROVIDER_REASONS else "correction_failed"
                    retry_after = float(getattr(exc, "retry_after", 0.0) or 0.0)
                    result = None
                pace.remaining = max(0.0, pace.remaining - (offered - call_pace.remaining))
                self._book_correction_usage(entry, batch_id, usage)
                if result is not None:
                    break
                # Bounded retry: only a rate limit, only once per batch, only a wait the provider named that fits the
                # per-wait cap and what is left of the shared allowance.
                if (failure == "rate_limited" and attempt + 1 < CORRECTION_ATTEMPTS
                        and 0.0 < retry_after <= min(CORRECTION_MAX_WAIT, pace.remaining)):
                    pace.remaining -= retry_after
                    self._sleep(retry_after)
                    continue
                # One request that is larger than the model's whole output allowance (a refusal with no window to wait for):
                # waiting does not help, asking for less does. The refusal taught the provider its limit, so the next attempt
                # re-reads the ceiling and sends a smaller batch at once, with no wait and no draw on the allowance. Only
                # when the ceiling really went down: the same request would be refused the same way.
                if (failure == "request_too_large" and attempt + 1 < CORRECTION_ATTEMPTS
                        and (correction_ceiling(self._corrector) or 0) > 0
                        and len(fit_correction_batch(batch, correction_ceiling(self._corrector))) < len(batch)):
                    continue
                # Groq cannot take this batch: a rate limit that will not be waited out (too long, or the attempts are
                # spent), a request that cannot shrink, a provider fault, or no Groq credential (D-224, PROPOSED). The
                # router's `media_transcript_correction` capability takes THAT batch, after its own spend check.
                if (result is None and self._fallback_corrector is not None
                        and (failure == "rate_limited" or failure in media_translation.FALLBACK_REASONS)):
                    result, failure = self._correct_via_fallback(
                        entry, batch_id, language, batch_cues, description, failure, retry_after, notes)
                break
            if skipped:
                continue
            if result is None:
                break
            problem = self._take_batch(language, batch, result, accepted, reasons, rejected, providers, models, model)
            if problem:
                failure = problem
                break
            succeeded += 1
        if failure:
            _logger.warning("transcript correction stopped for %s: %s", entry.media_id, failure)
            return ("partial" if succeeded else "failed"), failure
        return ("partial" if rejected else "applied"), ""

    @staticmethod
    def _usage_collector(captured: list[tuple[str, Any, str]]) -> Callable[..., None]:
        """What a provider's usage report is appended to: (model, usage, provider). A report without a provider is Groq's."""
        def collect(model: str, value: Any, provider: str = "groq") -> None:
            captured.append((model, value, provider))
        return collect

    def _book_ai_usage(
        self, entry: MediaLibraryEntry, batch_id: str, usage: list[tuple[str, Any, str]]
    ) -> dict[tuple[str, str], int]:
        """Book what each provider reported it billed, one ledger row per provider (a refused or failed call reports
        nothing), tagged with that provider so the free-tier and environment stamps are its own (D-219, D-221). Returns
        how many answers each (provider, model) served."""
        served: dict[tuple[str, str], int] = {}
        grouped: dict[str, list[tuple[str, Any]]] = {}
        for model, value, provider in usage:
            grouped.setdefault(provider, []).append((model, value))
            served[(provider, model)] = served.get((provider, model), 0) + 1
        usage.clear()
        for provider, items in grouped.items():
            actual = sum(self._ai_cost(model, value, provider) for model, value in items)
            self._ledger.record(KIND_AI, actual, batch_id=batch_id, media_id=entry.media_id, units=len(items), provider=provider)
        return served

    def _book_correction_usage(self, entry: MediaLibraryEntry, batch_id: str, usage: list[tuple[str, Any, str]]) -> None:
        self._book_ai_usage(entry, batch_id, usage)

    @staticmethod
    def _target_provider(engine: Any) -> str:
        """The provider whose price a pre-call estimate uses: the router's configured one, else Groq."""
        target = getattr(engine, "target", None)
        try:
            chosen = target() if callable(target) else None
        except Exception:  # noqa: BLE001
            chosen = None
        return str(chosen[0]) if chosen else "groq"

    def _fallback_ready(self) -> bool:
        target = getattr(self._fallback_corrector, "target", None)
        return callable(target) and target() is not None

    @staticmethod
    def _without_primary(**_kwargs: Any) -> Any:
        raise media_translation.TranslationProviderError("Groq is not configured.", reason="not_configured")

    def _admit_ai(self, batch_id: str) -> Callable[[str, str, int], None]:
        """The spend check run before each router call: the call's estimated cost at the router's own provider and model
        against the media caps, refusing it (`spend_cap`) before anything is sent (D-218's per-call rule)."""
        def admit(provider: str, model: str, tokens: int) -> None:
            try:
                self._ledger.check(KIND_AI, batch_id, self._ai_cost(
                    model, {"prompt_tokens": tokens, "completion_tokens": tokens}, provider))
            except SpendCapReached:
                raise media_translation.TranslationProviderError("spend cap", reason="spend_cap") from None
            except Exception:  # noqa: BLE001 - an unreadable ledger admits nothing
                raise media_translation.TranslationProviderError("spend check failed", reason="provider_error") from None
        return admit

    def _correct_via_fallback(
        self, entry: MediaLibraryEntry, batch_id: str, language: str, cues: tuple[Cue, ...], description: str, failure: str,
        retry_after: float = 0.0, notes: dict[str, str] | None = None,
    ) -> tuple[Any, str]:
        """One correction batch through the router. Returns (result, failure): the result when the router answered,
        else None with Groq's own reason kept (it says why the batch stopped). When the cap refused the router call,
        Groq's reason stays if it named a wait; `spend_cap` is the reason only when Groq's refusal was terminal too. The
        refusal is recorded as `transcript_correction_fallback_blocked` either way."""
        target = self._fallback_corrector.target()
        if target is None:
            return None, failure
        provider, model = target
        context_bytes = len(entry.title.encode("utf-8")) + len(description.encode("utf-8"))
        tokens = max(512, min(8192, sum(len(cue.text.encode("utf-8")) for cue in cues) + context_bytes + 1000))
        try:
            self._ledger.check(KIND_AI, batch_id, self._ai_cost(model, {"prompt_tokens": tokens, "completion_tokens": tokens}, provider))
        except SpendCapReached:
            if notes is not None:
                notes["fallback_blocked"] = "spend_cap"
            return None, (failure if retry_after > 0 else "spend_cap")
        except Exception:  # noqa: BLE001
            _logger.warning("transcript correction fallback could not be prepared for %s", entry.media_id, exc_info=True)
            return None, "correction_unavailable"
        usage: list[tuple[str, Any, str]] = []
        result: Any = None
        try:
            if self._translation_sink is not None:
                with self._translation_sink(self._usage_collector(usage)):
                    result = self._fallback_corrector.correct(language=language, cues=cues, title=entry.title, description=description)
            else:
                result = self._fallback_corrector.correct(language=language, cues=cues, title=entry.title, description=description)
        except Exception as exc:  # noqa: BLE001 - only the stable reason is kept, never the provider's message
            _logger.warning("transcript correction fallback failed for %s: %s", entry.media_id, str(getattr(exc, "reason", "") or type(exc).__name__))
            result = None
        self._book_ai_usage(entry, batch_id, usage)
        return (result, "") if result is not None else (None, failure)

    @staticmethod
    def _take_batch(
        language: str, batch: list[tuple[int, Cue]], result: Any, accepted: dict[int, str], reasons: dict[int, str],
        rejected: list[dict[str, Any]], providers: list[str], models: list[str], model: str,
    ) -> str:
        """Accept the valid cues of one batch result. Returns "" or `malformed_result` when it cannot be mapped to cues."""
        if not isinstance(result, Mapping):
            return "malformed_result"
        texts, edit_reasons = result.get("texts"), result.get("reasons")
        if (not isinstance(texts, (list, tuple)) or len(texts) != len(batch)
                or not isinstance(edit_reasons, (list, tuple)) or len(edit_reasons) != len(batch)
                or any(not isinstance(text, str) for text in texts)):
            return "malformed_result"
        from writing_coach.media_transcript_quality import repair_english_caption_text
        providers.append(str(result.get("provider") or "groq")[:80])
        models.append(str(result.get("model") or model)[:120])
        for (index, cue), proposed, why in zip(batch, texts, edit_reasons, strict=True):
            proposed = proposed.strip()
            if language == "en":
                # The model may re-add what the deterministic repair removed (`>>`, a sound tag): clean it the same way.
                proposed = repair_english_caption_text(proposed)
            code = reject_cue_edit(language, cue.text, proposed)
            unchanged = proposed == cue.text
            # A cue the model left as it was needs no reason: an invalid reason beside unchanged text is not an edit to refuse.
            if not code and not unchanged and (not isinstance(why, str) or not why.strip() or len(why.strip()) > 240):
                code = "malformed_result"
            if code:
                rejected.append({"index": index, "start_ms": cue.start_ms, "code": code, "before": cue.text[:1000], "proposed": proposed[:1000]})
                continue
            accepted[index] = proposed
            if unchanged:
                continue
            # Stored as a code from the closed list (the Admin screen words it in EN/VI/ZH); a sentence is never kept.
            reason_code = why.strip().casefold().replace("-", "_").replace(" ", "_")
            reasons[index] = reason_code if reason_code in media_translation.CORRECTION_REASON_CODES else "other"
        return ""

    def _finish_correction(
        self, store: Any, entry: MediaLibraryEntry, lines: list[Cue], baseline: list[tuple[int, Cue]], dropped: list[int],
        accepted: dict[int, str], reasons: dict[int, str], rejected: list[dict[str, Any]],
        providers: list[str], models: list[str], state: str, detail: str, notes: dict[str, str] | None = None,
    ) -> tuple[list[Cue], dict[str, Any]]:
        provider = ";".join(dict.fromkeys(providers))[:80]
        model = ";".join(dict.fromkeys(models))[:120]
        corrected: list[Cue] = []
        rows: list[dict[str, Any]] = []
        base = dict(baseline)
        for index in dropped:
            before = lines[index]
            rows.append({"index": index, "start_ms": before.start_ms, "end_ms": before.end_ms, "before": before.text[:1000],
                         "after": "", "reason": "", "reason_code": "noise_removed", "provider": "", "model": ""})
        for index, before in enumerate(lines):
            if index not in base:
                continue
            after = accepted[index]
            corrected.append(Cue(before.start_ms, before.end_ms, after))
            if after == before.text:
                continue
            by_model = after != base[index].text
            rows.append({"index": index, "start_ms": before.start_ms, "end_ms": before.end_ms,
                         "before": before.text[:1000], "after": after[:1000],
                         "reason": reasons.get(index, "")[:240] if by_model else "",
                         "reason_code": "model_edit" if by_model else "noise_removed",
                         "provider": provider if by_model else "", "model": model if by_model else ""})
        rows.sort(key=lambda row: row["index"])
        rejected.sort(key=lambda row: row["index"])
        if rejected and not detail:
            counts: dict[str, int] = {}
            for item in rejected:
                counts[item["code"]] = counts.get(item["code"], 0) + 1
            detail = max(counts, key=lambda code: (counts[code], code))
        fields = {"transcript_correction_state": state, "transcript_correction_detail": detail,
                  "transcript_corrections": rows, "transcript_correction_rejected": rejected}
        if notes and notes.get("fallback_blocked"):
            fields["transcript_correction_fallback_blocked"] = notes["fallback_blocked"]
        self._write_processing(store, store.get(entry.media_id) or entry, **fields)
        return corrected, fields

    def _correction_outcome(self, store: Any, entry: MediaLibraryEntry, state: str, detail: str) -> dict[str, Any]:
        fields = {"transcript_correction_state": state, "transcript_correction_detail": detail,
                  "transcript_corrections": [], "transcript_correction_rejected": []}
        self._write_processing(store, store.get(entry.media_id) or entry, **fields)
        return fields

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
            cause = getattr(getattr(exc, "__cause__", None), "reason", "")
            if cause == REASON_ZH_TRADITIONAL:
                return [], REASON_ZH_TRADITIONAL, "", "", ""
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
            # Title context only for short audio (ASR_PROMPT_MAX_SECONDS): a long item loses more than a prompt gains.
            prompt = (build_asr_prompt(entry.title, str((entry.source or {}).get("description") or ""), language=entry.language)
                      if total <= ASR_PROMPT_MAX_SECONDS else "")
            for path, offset in chunks:
                estimate = self._ledger.asr_estimate(_probe_seconds(path))
                try:
                    self._ledger.check(KIND_ASR, batch_id, estimate)
                except SpendCapReached as capped:
                    raise PipelineStop(capped.code, f"{capped.spent:.2f}/{capped.limit:.2f} USD") from capped
                result = self._recognise(path, entry, prompt)
                # What was billed is the audio the provider processed, at least the provider's minimum.
                self._ledger.record(KIND_ASR, estimate, batch_id=batch_id, media_id=entry.media_id, units=_probe_seconds(path), provider="groq")
                cost += estimate
                if prompt and asr_text_has_junk("".join(segment.text for segment in result.segments) or result.text):
                    # The prompt misled this chunk (full-width junk): listen again without it, once. The extra call is
                    # checked against the cap and booked like the first.
                    try:
                        self._ledger.check(KIND_ASR, batch_id, estimate)
                    except SpendCapReached as capped:
                        raise PipelineStop(capped.code, f"{capped.spent:.2f}/{capped.limit:.2f} USD") from capped
                    result = self._recognise(path, entry, "")
                    self._ledger.record(KIND_ASR, estimate, batch_id=batch_id, media_id=entry.media_id, units=_probe_seconds(path), provider="groq")
                    cost += estimate
                results.append((result, offset))
        cues, words, detected, screen = _asr_cues(results, entry.language)
        if not cues:
            raise PipelineStop("empty_transcript", f"{screen['filtered']} filtered" if screen["filtered"] else "")
        return cues, words, detected, cost, total, screen

    def _recognise(self, path: Path, entry: MediaLibraryEntry, prompt: str) -> SpeechAsrResult:
        try:
            return self._asr.transcribe_bytes(
                path.read_bytes(), filename=path.name, content_type="audio/mpeg",
                language=primary_language(entry.language) or None, prompt=prompt or None,
            )
        except SpeechAsrTimedOut as exc:
            raise PipelineStop("asr_timeout") from exc
        except SpeechAsrRequestFailed as exc:
            status = getattr(exc, "status_code", None)
            code = "asr_rate_limited" if status == 429 else "asr_auth" if status in {401, 403} else "asr_failed"
            raise PipelineStop(code) from exc
        except (SpeechAsrMalformed, SpeechAsrPayloadTooLarge) as exc:
            raise PipelineStop("asr_failed") from exc

    def _audio_source(self, assets: BookAssetStore, entry: MediaLibraryEntry, work: Path, max_seconds: int) -> Path:
        if entry.provider == "youtube":
            if self._youtube_audio is None:
                raise PipelineStop("audio_unavailable")
            from writing_coach.media_providers.youtube_audio import scrubbed_error

            try:
                return Path(self._youtube_audio(entry.canonical_url, work, max_seconds=max_seconds))
            except PipelineStop:
                raise
            except Exception as exc:  # noqa: BLE001 - the provider refused or timed out; reported as one reason
                _logger.warning("audio download failed for %s: %s", entry.media_id, scrubbed_error(exc))
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
        guard: Callable[[], None] | None = None, pacing_seconds: float | None = None,
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
        # The one budget of seconds the provider may wait inside a call for its output-token window (D-218): shared by all
        # the rounds of this run, so a stuck window cannot hold the worker beyond it.
        pace = media_translation.PacingBudget(max_total_wait if pacing_seconds is None else pacing_seconds)
        served: dict[tuple[str, str], int] = {}   # which (provider, model) answered how many requests of this run
        blocked: dict[str, str] = {}              # why a router call was refused in this run (`fallback_blocked`)
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
                usage: list[tuple[str, Any, str]] = []
                retry_after = 0.0
                scope_notes: dict[str, str] = {}
                try:
                    # The scope lets a batch Groq cannot take go to the router (D-224, PROPOSED): a rate-limit wait longer
                    # than TRANSLATION_MAX_WAIT counts as one; each router call is spend-checked first.
                    with media_translation.translation_pacing(pace), media_translation.fallback_scope(
                            TRANSLATION_MAX_WAIT, self._admit_ai(batch_id)) as granted:
                        scope_notes = granted.notes
                        if self._translation_sink is not None:
                            with self._translation_sink(self._usage_collector(usage)):
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
                    for key, count in self._book_ai_usage(entry, batch_id, usage).items():
                        served[key] = served.get(key, 0) + count
                blocked.update(scope_notes)
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
        self._record_translation_served(store, entry, served, blocked.get("fallback_blocked", ""))
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
            max_rounds=CONTINUATION_ROUNDS, max_total_wait=0.0, guard=guard, pacing_seconds=CONTINUATION_PACING_SECONDS,
        )
        fresh = store.get(entry.media_id) or entry
        outcome = self._defer_translation(store, fresh, outcome, stop)
        fields: dict[str, Any] = {"translation": outcome, "translation_counts": counts}
        if outcome != "deferred":
            fields["translation_continuation"] = {}
        self._write_processing(store, fresh, **fields)

    def _record_translation_served(
        self, store: Any, entry: MediaLibraryEntry, served: Mapping[tuple[str, str], int], blocked: str = "",
    ) -> None:
        """Which provider and model answered the translation requests, beside `translation_counts` (D-224): the Admin
        item view and the cost page read it. Counts add up across a continuation; nothing but names and counts is kept.
        `blocked` is why a router call was refused in this run (`spend_cap`), kept as `translation_fallback_blocked`."""
        if not served and not blocked:
            return
        try:
            fresh = store.get(entry.media_id) or entry
            totals: dict[tuple[str, str], int] = {}
            for row in (fresh.processing or {}).get("translation_served") or ():
                if isinstance(row, Mapping):
                    key = (str(row.get("provider") or "")[:40], str(row.get("model") or "")[:120])
                    totals[key] = totals.get(key, 0) + int(row.get("requests") or 0)
            for (provider, model), count in served.items():
                key = (provider[:40], model[:120])
                totals[key] = totals.get(key, 0) + count
            rows = [{"provider": provider, "model": model, "requests": count} for (provider, model), count in totals.items()]
            fields: dict[str, Any] = {"translation_served": rows}
            if blocked:
                fields["translation_fallback_blocked"] = blocked
            self._write_processing(store, entry, **fields)
        except PipelineStop:
            raise
        except Exception:  # noqa: BLE001 - a convenience; the lesson stands without it
            _logger.warning("translation provider record not written for %s", entry.media_id, exc_info=True)

    def _record_translation_reason(self, store: Any, entry: MediaLibraryEntry, reason: str) -> None:
        """Why the translation stopped short, beside `translation_counts`: a stable code, never log prose."""
        try:
            self._write_processing(store, entry, translation_reason=reason)
        except PipelineStop:
            raise
        except Exception:  # noqa: BLE001 - the reason is a convenience; the lesson stands without it
            _logger.warning("translation reason not written for %s", entry.media_id, exc_info=True)

    def _ai_cost(self, model: str, usage: Any, provider: str = "groq") -> float:
        usage = usage if isinstance(usage, Mapping) else {}
        # A model with a published media rate is rated at it (D-218), before the catalogue, whose free-plan zero entries
        # (qwen/qwen3.8-27b) would book 0 and leave every spend cap unreachable. The rate table is Groq's.
        rate = policies.media_ai_model_rate(model) if provider == "groq" else None
        prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if rate is not None and type(prompt) is int and type(completion) is int and prompt >= 0 and completion >= 0:
            return (prompt * rate[0] + completion * rate[1]) / 1_000_000
        priced = estimate_token_cost(provider, model, usage)
        # A zero from the catalogue is a free-plan fact about another capability, not a price for this ledger: it falls
        # through to the flat rate below.
        if priced.get("state") == "estimated" and isinstance(priced.get("amount"), (int, float)) and float(priced["amount"]) > 0:
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
