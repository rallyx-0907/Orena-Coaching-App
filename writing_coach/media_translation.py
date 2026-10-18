"""Provider-neutral, cached shared-media translation."""

from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
import json
import logging
import math
import os
import re
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Protocol

import requests

from writing_coach.core.support_languages import support_language, normalize_support_language
from writing_coach.media_ingestion import primary_language
from writing_coach.media_learning import (
    MediaLearningContractError,
    MediaLearningObject,
    SegmentTranslation,
    TranscriptSegment,
)

_logger = logging.getLogger(__name__)

MAX_TRANSLATION_BATCH_SEGMENTS = 24
MAX_TRANSLATION_BATCH_CHARS = 6_000
MAX_TRANSLATION_BATCHES = 8

# How much completion capacity one translation request may reserve.
#
# Derived from the batch bounds above rather than picked: a batch is at most
# MAX_TRANSLATION_BATCH_CHARS of source, and the JSON envelope adds roughly 60
# characters per segment, so a worst-case batch produces on the order of a few
# thousand output tokens. 2048 covers a normal transcript batch while leaving
# most of an 8000-token ceiling for the prompt - the previous 8000 reserved the
# entire budget and left none, which is what produced HTTP 413.
#
# It is a reservation, not a target: a request that needs less simply uses less.
GROQ_MAX_COMPLETION_TOKENS_ENV = "GROQ_TRANSLATION_MAX_COMPLETION_TOKENS"
DEFAULT_GROQ_MAX_COMPLETION_TOKENS = 2048
MIN_GROQ_MAX_COMPLETION_TOKENS = 256
MAX_GROQ_MAX_COMPLETION_TOKENS = 8192
# How many times an over-large batch may be halved before giving up truthfully.
MAX_TRANSLATION_SPLIT_DEPTH = 3

# An output-tokens-per-minute (OTPM) allowance, which a provider may apply on top of its total-token one (D-218). The trial's
# `qwen/qwen3.8-27b` refused with "(OTPM): Limit 1000, Used 867, Requested 640": a request is admitted only while the output
# tokens used in the last minute plus the ones it reserves (`max_completion_tokens`) fit the limit. Nothing here names a
# model: the limit is configured (`GROQ_TRANSLATION_OUTPUT_TOKENS_PER_MINUTE`) or read from the provider's own refusal.
GROQ_OTPM_ENV = "GROQ_TRANSLATION_OUTPUT_TOKENS_PER_MINUTE"
MAX_OTPM_LIMIT = 10_000_000
OTPM_WINDOW_SECONDS = 60.0
# After a refusal the wait covers a whole window plus this, whatever `retry-after` said: the window that refused is not
# clear before then, and asking sooner only fills it again.
OTPM_MARGIN_SECONDS = 2.0
# One request reserves at most this share of the limit, so two fit a minute (a request as large as the limit leaves the
# minute idle between requests).
OTPM_REQUEST_SHARE = 2
MAX_SALVAGED_LINES = 512
# Why a model changed a transcript line: a closed list, so the Admin screen words each reason in its own language (EN, VI,
# ZH) instead of showing a sentence in whatever language the model chose. `other` is what any unlisted answer is stored as.
CORRECTION_REASON_CODES = (
    "punctuation", "capitalization", "spacing", "homophone", "idiom", "proper_noun", "no_change", "other",
)

# Time is read and slept through these two so a test can drive a virtual clock.
_monotonic: Callable[[], float] = time.monotonic
_pause: Callable[[float], None] = time.sleep


class _RequestTooLarge(Exception):
    """The provider refused this request for its size, not its timing."""


# Who is listening for the tokens a provider answer billed. A caller that books spend (the media pipeline) opens
# `usage_sink` around its translation call; every answer the provider returned with `usage` reports it there, and a
# refused call (401/403/429), a timeout or an answer without `usage` reports nothing, so nothing is booked for it (#228).
# It is a ContextVar: moving translation to another thread or executor needs `contextvars.copy_context().run(...)`, or
# usage arrives empty there and the spend cap stops biting (nothing is booked).
_USAGE_SINK: ContextVar[Callable[[str, dict], None] | None] = ContextVar("media_translation_usage_sink", default=None)


@contextmanager
def usage_sink(callback: Callable[[str, dict], None]) -> Iterator[None]:
    token = _USAGE_SINK.set(callback)
    try:
        yield
    finally:
        _USAGE_SINK.reset(token)


def _wire_segments(segments: TranslationBatch) -> tuple[tuple[TranslatableSegment, ...], dict[str, str]]:
    """What travels to the provider, and the map back to the canonical ids.

    Canonical provenance IDs contain hashes. Echoing those in every JSON row wastes generation capacity; short
    request-local handles retain exact identity while keeping the provider response bounded."""
    compact = any(len(segment.segment_id) > 64 for segment in segments)
    wire = tuple(
        _TranslationLine(f"line-{index:06d}", segment.original_text) if compact else segment
        for index, segment in enumerate(segments)
    )
    return wire, {w.segment_id: original.segment_id for w, original in zip(wire, segments, strict=True)}


def _output_chars(wire: tuple[TranslatableSegment, ...]) -> int:
    """A generous bound on the JSON the provider will write back: the id, the text twice over, and the envelope."""
    return sum(len(s.segment_id) + 2 * len(s.original_text) + 64 for s in wire)


def estimate_output_tokens(segments: TranslationBatch) -> int:
    """The completion room a batch reserves (two characters a token); the same bound `_completion_budget` uses."""
    return math.ceil(_output_chars(_wire_segments(segments)[0]) / 2)


def group_by_output_tokens(segments: TranslationBatch, cap: int) -> tuple[TranslationBatch, ...]:
    """Consecutive groups whose reserved completion room each fits `cap` (a lone line larger than `cap` is its own group)."""
    groups: list[TranslationBatch] = []
    current: list[TranslatableSegment] = []
    used = 0
    for segment in segments:
        compact = len(segment.segment_id) > 64
        size = math.ceil(((11 if compact else len(segment.segment_id)) + 2 * len(segment.original_text) + 64) / 2)
        if current and used + size > cap:
            groups.append(tuple(current))
            current, used = [], 0
        current.append(segment)
        used += size
    if current:
        groups.append(tuple(current))
    return tuple(groups)


def resolve_output_tokens_per_minute(value: int | None = None, env: Mapping[str, str] | None = None) -> int | None:
    """The configured OTPM limit, or None when none is set or it cannot be read (the provider's refusal then teaches it)."""
    if value is None:
        values = os.environ if env is None else env
        raw = str(values.get(GROQ_OTPM_ENV, "")).strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 < value <= MAX_OTPM_LIMIT:
        return None
    return value


class OutputTokenWindow:
    """What this process has asked a model to write in the last minute, against the model's OTPM limit (when known).

    A request reserves its `max_completion_tokens` when it is sent; a refusal that reports the provider's own `Used` count
    corrects the window. The provider's allowance is per organisation and model, so every provider object for one model
    shares one window (`output_window`)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._limit: int | None = None
        self._blocked_until = 0.0
        self._events: list[list[float]] = []   # [time, tokens], oldest first

    @property
    def limit(self) -> int | None:
        return self._limit

    def set_limit(self, limit: int | None) -> None:
        with self._lock:
            self._limit = limit if limit and limit > 0 else self._limit

    def _prune(self, now: float) -> None:
        horizon = now - OTPM_WINDOW_SECONDS - OTPM_MARGIN_SECONDS
        self._events = [event for event in self._events if event[0] > horizon]

    def used(self, now: float) -> int:
        with self._lock:
            self._prune(now)
            return int(sum(event[1] for event in self._events))

    def wait_for(self, tokens: int, now: float) -> float:
        """Seconds until `tokens` more fit under the limit; 0 when they fit now or no limit is known."""
        with self._lock:
            if self._limit is None:
                return 0.0
            self._prune(now)
            held = max(0.0, self._blocked_until - now)
            excess = sum(event[1] for event in self._events) + tokens - self._limit
            if excess <= 0:
                return held
            freed = 0.0
            for at, spent in self._events:
                freed += spent
                if freed >= excess:
                    return max(held, at + OTPM_WINDOW_SECONDS + OTPM_MARGIN_SECONDS - now)
            return max(held, OTPM_WINDOW_SECONDS + OTPM_MARGIN_SECONDS)

    def reserve(self, tokens: int, now: float) -> list[float]:
        event = [now, float(tokens)]
        with self._lock:
            self._events.append(event)
        return event

    def block_until(self, moment: float) -> None:
        """The provider refused: nothing is sent before `moment`, even a request that would fit what is known."""
        with self._lock:
            self._blocked_until = max(self._blocked_until, moment)

    def release(self, event: list[float]) -> None:
        with self._lock:
            self._events = [item for item in self._events if item is not event]

    def sync_used(self, used: int, now: float) -> None:
        """The provider said how much of the minute is spent: if that is more than this process knows, the rest was spent
        elsewhere (another worker, an earlier run) and is counted from now, so it is waited out in full."""
        with self._lock:
            self._prune(now)
            known = sum(event[1] for event in self._events)
            if used > known:
                self._events.append([now, float(used - known)])


_WINDOWS: dict[str, OutputTokenWindow] = {}
_WINDOWS_LOCK = threading.Lock()


def output_window(model: str) -> OutputTokenWindow:
    with _WINDOWS_LOCK:
        return _WINDOWS.setdefault(str(model), OutputTokenWindow())


def reset_output_windows() -> None:
    with _WINDOWS_LOCK:
        _WINDOWS.clear()


class PacingBudget:
    """How many seconds a caller lets the provider wait inside one call for the allowance to refill."""

    def __init__(self, seconds: float) -> None:
        self.remaining = max(0.0, float(seconds))


_PACING: ContextVar[PacingBudget | None] = ContextVar("media_translation_pacing", default=None)


@contextmanager
def translation_pacing(seconds: float | PacingBudget) -> Iterator[PacingBudget]:
    """Within this block a provider may sleep up to `seconds` in total for an output-token window to clear. Outside it, or
    once the budget is spent, a request that does not fit is refused at once (`rate_limited`, with the exact wait) and is
    never sent: the caller decides when to ask again."""
    budget = seconds if isinstance(seconds, PacingBudget) else PacingBudget(seconds)
    token = _PACING.set(budget)
    try:
        yield budget
    finally:
        _PACING.reset(token)


_ORG_ID = re.compile(r"org_[A-Za-z0-9]+")
_OTPM_REFUSAL = re.compile(r"\(OTPM\)\s*:\s*Limit\s+(\d+)\s*,\s*Used\s+(\d+)", re.IGNORECASE)


def _error_message(response: object) -> str:
    try:
        payload = response.json()  # type: ignore[attr-defined]
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = error.get("message", "") if isinstance(error, dict) else ""
    except Exception:  # noqa: BLE001 - a log line never fails the call
        return ""
    return " ".join(str(message).split())


def _error_detail(response: object) -> str:
    """The provider's own sentence about a refusal (which allowance, how much was left), short and on one line.
    It names limits and counts, never a credential; empty when the answer carries none."""
    # An organisation id is an account identifier, not a limit: it stays out of the log.
    return _ORG_ID.sub("org_<redacted>", _error_message(response))[:240]


def _otpm_refusal(response: object) -> tuple[int, int] | None:
    """(limit, used) when a 429 says the output-tokens-per-minute allowance refused the request, else None."""
    found = _OTPM_REFUSAL.search(_error_message(response))
    return (int(found.group(1)), int(found.group(2))) if found else None


# The second sentence Groq answers with (seen live 2026-10-18, `qwen/qwen3.8-27b`): one request alone expects more output than
# the whole per-minute allowance, so there is no `Used` count - the minute is not the problem, the request is. Same limit, a
# different remedy: ask for less, do not wait for a window to clear.
_OTPM_TOO_LARGE = re.compile(r"\(OTPM\)\s*:\s*Limit\s+(\d+)\s*,\s*Requested\s+(\d+)", re.IGNORECASE)


def _otpm_request_too_large(response: object) -> tuple[int, int] | None:
    """(limit, requested) when a 429 says this one request is larger than the output-tokens-per-minute allowance, else None."""
    found = _OTPM_TOO_LARGE.search(_error_message(response))
    return (int(found.group(1)), int(found.group(2))) if found else None


@dataclass(frozen=True)
class _TranslationLine:
    segment_id: str
    original_text: str


def _is_request_too_large(response: object) -> bool:
    """Whether a 413 is a sizing refusal, read from structured JSON fields.

    Groq returns its own error envelope; the code is read from it rather than
    by matching prose. A 413 without a readable envelope is still treated as a
    sizing refusal, because that is what the status itself means.
    """

    try:
        payload = response.json()  # type: ignore[attr-defined]
    except Exception:
        return True
    error = payload.get("error", payload) if isinstance(payload, dict) else {}
    if not isinstance(error, dict):
        return True
    return str(error.get("code") or "") in {"rate_limit_exceeded", "request_too_large", ""}


def resolve_max_completion_tokens(
    value: int | None = None, env: Mapping[str, str] | None = None
) -> int:
    """A positive, bounded completion reservation.

    An out-of-range or unparseable configuration falls back to the default
    rather than silently reserving an absurd amount of capacity.
    """

    if value is None:
        values = os.environ if env is None else env
        raw = str(values.get(GROQ_MAX_COMPLETION_TOKENS_ENV, "")).strip()
        if not raw:
            return DEFAULT_GROQ_MAX_COMPLETION_TOKENS
        try:
            value = int(raw)
        except ValueError:
            return DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    if not isinstance(value, int) or isinstance(value, bool):
        return DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    if value < MIN_GROQ_MAX_COMPLETION_TOKENS or value > MAX_GROQ_MAX_COMPLETION_TOKENS:
        return DEFAULT_GROQ_MAX_COMPLETION_TOKENS
    return value
MAX_TRANSLATION_CACHE_ENTRIES = 128


class MediaTranslationStatus(StrEnum):
    READY = "ready"
    NOT_REQUIRED = "not_required"
    TRANSCRIPT_UNAVAILABLE = "transcript_unavailable"
    TOO_LARGE = "too_large"
    UNAVAILABLE = "unavailable"


class MediaTranslationFailureKind(StrEnum):
    EXECUTION_UNAVAILABLE = "execution_unavailable"
    MALFORMED_RESULT = "malformed_result"


@dataclass(frozen=True)
class MediaTranslationProvenance:
    capability_key: str
    provider: str | None
    model: str | None
    request_count: int


@dataclass(frozen=True)
class MediaTranslationResult:
    media_object: MediaLearningObject
    status: MediaTranslationStatus
    target_language: str
    provenance: MediaTranslationProvenance | None = None
    failure_kind: MediaTranslationFailureKind | None = None
    # Why a non-ready result stopped, as a stable machine code (`rate_limited`, `provider_error`, ...), and how long the
    # provider asked to be left alone, in seconds. Empty when the result is ready.
    reason: str = ""
    retry_after: float = 0.0


class TranslationProviderError(RuntimeError):
    """A provider failure. `reason` is the stable code an operator sees; `retry_after` is the wait the provider asked for."""

    def __init__(self, message: str = "", *, reason: str = "provider_error", retry_after: float = 0.0) -> None:
        super().__init__(message)
        self.reason = reason
        self.retry_after = max(0.0, float(retry_after or 0.0))


_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


def _retry_after_seconds(headers: Mapping[str, str]) -> float:
    """The wait a rate-limited provider asked for: `Retry-After` seconds, else Groq's `x-ratelimit-reset-*` ("2m3.5s")."""
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    try:
        return max(0.0, float(lowered["retry-after"]))
    except (KeyError, ValueError):
        pass
    waits = []
    for key in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests"):
        parts = _DURATION_PART.findall(lowered.get(key, ""))
        if parts:
            scale = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
            waits.append(sum(float(number) * scale[unit] for number, unit in parts))
    return max(waits) if waits else 0.0


class TranslatableSegment(Protocol):
    """What an engine reads from a segment: its id and its text, never its timing.

    A transcript segment is one; a reading paragraph is another, and has no
    timing to invent.
    """

    @property
    def segment_id(self) -> str: ...

    @property
    def original_text(self) -> str: ...


TranslationBatch = tuple[TranslatableSegment, ...]


class TranslationProvider(Protocol):
    engine_id: str
    model_version: str

    def translate_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
    ) -> dict[str, str]: ...


class LocalHttpTranslationProvider:
    """Small application-side adapter for the isolated local Marian service."""

    engine_id = "local_marian"
    model_version = "opus-mt-v1"
    accepts_timeout = True  # a word lookup passes a short per-call timeout; other callers keep the 90 s default

    def __init__(self, base_url: str, *, timeout_seconds: float = 90.0) -> None:
        self._url = base_url.rstrip("/") + "/translate"
        self._timeout = timeout_seconds

    def translate_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
        *,
        timeout: float | None = None,
    ) -> dict[str, str]:
        payload = {
            "source_language": primary_language(source_language),
            "target_language": target_language,
            "segments": [
                {"segment_id": segment.segment_id, "text": segment.original_text}
                for segment in segments
            ],
        }
        try:
            response = requests.post(self._url, json=payload, timeout=timeout if timeout is not None else self._timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise TranslationProviderError("Local translation is unavailable.", reason="provider_timeout" if isinstance(exc, requests.Timeout) else "provider_error") from exc
        items = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise TranslationProviderError("Local translation returned invalid data.")
        translated: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                raise TranslationProviderError("Local translation returned invalid data.")
            segment_id = item.get("segment_id")
            meaning = item.get("translated_meaning")
            if not isinstance(segment_id, str) or segment_id in translated or not isinstance(meaning, str) or not meaning.strip():
                raise TranslationProviderError("Local translation returned invalid data.")
            translated[segment_id] = meaning.strip()
        return translated


TRANSLATION_PROVIDER_IDS = ("groq", "local")


def resolve_translation_provider_id(configured: str, *, groq_key: str) -> str:
    """Which engine translates, decided once from configuration.

    An empty value means "not configured", not "invalid": compose passes every
    optional variable through as an empty string, and `os.getenv(name, default)`
    only falls back when the name is absent entirely. Getting that wrong stops
    the application from importing at all.
    """
    chosen = str(configured or "").strip().casefold()
    if not chosen:
        chosen = "groq" if str(groq_key or "").strip() else "local"
    if chosen not in TRANSLATION_PROVIDER_IDS:
        raise ValueError(
            "MEDIA_TRANSLATION_PROVIDER must be "
            + " or ".join(repr(item) for item in TRANSLATION_PROVIDER_IDS)
            + "."
        )
    if chosen == "groq" and not str(groq_key or "").strip():
        raise ValueError("MEDIA_TRANSLATION_PROVIDER='groq' requires GROQ_API_KEY.")
    return chosen


class GroqTranslationProvider:
    """Translation through Groq's OpenAI-compatible chat API.

    The default provider since P2 of the AI cost plan. Measured against this
    account, a batch answers in about a second where the local model needed
    thirty-seven seconds a segment.

    Two things learned by measurement rather than from documentation, and both
    encoded here:

    - `response_format: json_object` is what keeps a reasoning model from
      spending its whole token budget thinking and returning an empty string.
      Without it, `openai/gpt-oss-*` answers "" and no error.
    - `reasoning_effort` is deliberately **not** sent. It is unnecessary in JSON
      mode, and other Groq models reject it outright with HTTP 400
      (`qwen3.6` accepts only `none`/`default`; `groq/compound` refuses it), so
      sending it would break the moment the model is changed.

    A failure raises `TranslationProviderError` and stops there. Choosing another
    provider is an operator decision, never something this class does on its own
    (`ARCHITECTURE_INVARIANTS.md`: no provider-to-provider fallback).
    """

    engine_id = "groq"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "openai/gpt-oss-120b",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: float = 90.0,
        max_completion_tokens: int | None = None,
        output_tokens_per_minute: int | None = None,
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self._model = str(model or "").strip()
        self._url = str(base_url or "").rstrip("/") + "/chat/completions"
        self._timeout = timeout_seconds
        self.model_version = self._model
        self._max_completion_tokens = resolve_max_completion_tokens(max_completion_tokens)
        # The model's output-token allowance: configured, else learned from the provider's own refusal, else unknown.
        self._otpm = output_window(self._model)
        configured = resolve_output_tokens_per_minute(output_tokens_per_minute)
        if configured is not None:
            self._otpm.set_limit(configured)
        # Lines translated by a batch that then stopped on a rate limit: asked for again, they are not paid for twice.
        self._salvaged: OrderedDict[tuple[str, str, str, str], str] = OrderedDict()
        self._salvage_lock = threading.Lock()
        # The last response's quota headers, so an admin surface can report the
        # budget before it runs out rather than after.
        self.last_quota: dict[str, str] = {}

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._model)

    def _language_name(self, code: str) -> str:
        """Human-readable name from the canonical registry, never a local map.

        A private mapping here recreated the three-language assumption L2.5
        removed everywhere else: any language outside vi/en/zh reached the
        prompt as a bare code, so Spanish was asked for "into natural es".
        There is one language registry for the product, not one per provider.
        """

        definition = support_language(code)
        return definition.translation_label if definition else str(code or "")

    def _prompt(self, source_language: str, target_language: str, segments: TranslationBatch) -> str:
        lines = "\n".join(
            f"{segment.segment_id}\t{segment.original_text}" for segment in segments
        )
        return (
            f"Translate each {self._language_name(source_language)} line into natural "
            f"{self._language_name(target_language)} for a language learner.\n"
            "Each input line is an id, a tab, then the text. Translate the text only.\n"
            "Return every id exactly once, unchanged.\n\n"
            f"{lines}"
        )

    def translate_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
    ) -> dict[str, str]:
        """Translate one batch, splitting it if the provider says it is too large.

        A 413 `rate_limit_exceeded` where Requested exceeds Limit is a sizing
        problem, not a transient one: retrying the identical request after a
        reset would fail again. Splitting is deterministic and preserves every
        segment id, so no line is lost or reordered. An ordinary 429 stays a
        transient rate limit and is not handled here.
        """

        if not self.configured:
            raise TranslationProviderError("Groq translation is not configured.", reason="not_configured")
        kept = {segment.segment_id: text for segment in segments
                if (text := self._salvage_get(source_language, target_language, segment)) is not None}
        pending = tuple(segment for segment in segments if segment.segment_id not in kept)
        merged = dict(kept)
        groups = group_by_output_tokens(pending, self._reservation_cap()) if self.batch_output_ceiling() is not None else (pending,)
        for group in (group for group in groups if group):
            try:
                merged.update(self._translate_batch(source_language, target_language, group, depth=0))
            except TranslationProviderError:
                self._salvage_put(source_language, target_language, segments, merged)   # finished groups are kept
                raise
        self._salvage_drop(source_language, target_language, segments)
        return {segment.segment_id: merged[segment.segment_id] for segment in segments}

    def correct(
        self, *, language: str, cues: tuple[Any, ...], title: str = "", description: str = ""
    ) -> dict[str, object]:
        """Make one bounded, metered correction request for an admin transcript.

        This deliberately does not use translation batching/retry or another
        model. It shares this provider's configured model, Groq transport,
        structured response mode, output allowance, and token usage ledger.
        """
        if not self.configured:
            raise TranslationProviderError("Groq translation is not configured.", reason="not_configured")
        texts = tuple(str(getattr(cue, "text", "")) for cue in cues)
        if not texts or len(texts) > 24 or sum(len(text) for text in texts) > 6_000:
            raise TranslationProviderError("Transcript correction batch exceeds its bound.", reason="request_too_large")
        language_name = self._language_name(language)
        if language.casefold().split("-", 1)[0] == "en":
            instructions = (
                "Repair English transcript presentation only: punctuation, capitalization, and spacing. "
                "Every spoken word and number must remain unchanged; do not add or remove any word."
            )
        else:
            instructions = (
                "Conservatively correct clear homophone or idiom recognition errors in this Simplified Chinese transcript. "
                "Do not rewrite style, infer unheard speech, or change line order. Keep uncertain text unchanged."
            )
        numbered = "\n".join(f"{index}\t{text}" for index, text in enumerate(texts))
        context = "\n".join(part for part in (
            f"Source title: {title[:180]}" if title else "",
            f"Source description: {description[:240]}" if description else "",
        ) if part)
        user = (
            f"Language: {language_name}.\n{context}\n"
            "Correct each line independently. Return JSON only as "
            "{\"lines\":[{\"index\":0,\"text\":\"...\",\"reason\":\"...\"}]}. "
            "The reason of each line must be exactly one code from this list, never a sentence: "
            f"{', '.join(CORRECTION_REASON_CODES)}. Use no_change for unchanged text. "
            "Return each index exactly once and preserve the input count and order.\n\n"
            f"{numbered}"
        )
        wanted = set(range(len(texts)))
        output_bound = sum(len(text.encode("utf-8")) for text in texts) + 80 * len(texts)
        max_tokens = min(self._reservation_cap(), max(256, output_bound))
        body = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "max_completion_tokens": max_tokens,
        }
        reserved = self._reserve_output(max_tokens)
        started = time.perf_counter()
        answered = False
        try:
            response = requests.post(
                self._url, json=body,
                headers={"Authorization": f"Bearer {self._api_key}"}, timeout=self._timeout,
            )
            self.last_quota = {
                key.lower(): value for key, value in response.headers.items()
                if key.lower().startswith("x-ratelimit-")
            }
            if response.status_code in {401, 403, 429}:
                asked = _retry_after_seconds(response.headers)
                too_large = False
                if response.status_code == 429:
                    asked = self._learn_from_refusal(response, reserved, asked)
                    too_large = _otpm_request_too_large(response) is not None
                if too_large:
                    # The request itself exceeds the allowance: waiting does not help, asking for less does. The limit is
                    # learned above, so the caller's next `correction_output_ceiling()` is smaller; no wait is asked for.
                    error = TranslationProviderError(
                        "Groq transcript correction request exceeds the output allowance.",
                        reason="request_too_large", retry_after=0.0,
                    )
                else:
                    error = TranslationProviderError(
                        "Groq transcript correction is rate limited." if response.status_code == 429
                        else "Groq refused the configured credentials.",
                        reason="rate_limited" if response.status_code == 429 else "provider_auth",
                        retry_after=asked,
                    )
                self._record(started, "failure", None, error)
                raise error
            response.raise_for_status()
            envelope = response.json()
            answered = True
            self._record(started, "success", envelope.get("usage") if isinstance(envelope, dict) else None)
            choice = envelope["choices"][0]
            if choice.get("finish_reason") == "length":
                raise TranslationProviderError("Groq transcript correction output was truncated.", reason="malformed_result")
            data = json.loads(choice["message"]["content"])
        except TranslationProviderError:
            raise
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            if not answered:
                self._record(started, "failure", None, exc)
            reason = "provider_timeout" if isinstance(exc, requests.Timeout) else "provider_error"
            raise TranslationProviderError("Groq transcript correction is unavailable.", reason=reason) from exc
        rows = data.get("lines") if isinstance(data, dict) else None
        if not isinstance(rows, list) or len(rows) != len(texts):
            raise TranslationProviderError("Groq returned malformed transcript corrections.", reason="malformed_result")
        result: dict[int, tuple[str, str]] = {}
        for row in rows:
            if not isinstance(row, dict) or type(row.get("index")) is not int or row["index"] not in wanted:
                raise TranslationProviderError("Groq returned malformed transcript corrections.", reason="malformed_result")
            index = row["index"]
            text = row.get("text")
            reason = row.get("reason")
            if (index in result or not isinstance(text, str) or not text.strip()
                    or len(text) > max(200, 2 * len(texts[index]) + 24)
                    or not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 240):
                raise TranslationProviderError("Groq returned malformed transcript corrections.", reason="malformed_result")
            # The reason is a code from a closed list the operator's screen words in its own language; whatever else the
            # model writes (a sentence in any language) is stored as the neutral `other`, never shown as free text.
            code = reason.strip().casefold().replace("-", "_").replace(" ", "_")
            result[index] = (text.strip(), code if code in CORRECTION_REASON_CODES else "other")
        if set(result) != wanted:
            raise TranslationProviderError("Groq returned malformed transcript corrections.", reason="malformed_result")
        return {"texts": [result[index][0] for index in range(len(texts))],
                "reasons": [result[index][1] for index in range(len(texts))], "provider": self.engine_id,
                "model": self._model}

    def batch_output_ceiling(self) -> int | None:
        """The most completion room one request should reserve so two fit a minute, or None while no output-token limit is
        known. A caller that cuts a transcript into batches sizes them to this (D-218)."""
        limit = self._otpm.limit
        return None if limit is None else max(1, limit // OTPM_REQUEST_SHARE)

    def _reservation_cap(self) -> int:
        ceiling = self.batch_output_ceiling()
        return self._max_completion_tokens if ceiling is None else min(self._max_completion_tokens, ceiling)

    def correction_output_ceiling(self) -> int:
        """The most output tokens one transcript-correction request can really be given: the configured per-request
        completion cap, and when the model's output-token allowance is known, its per-request share of the minute. A
        batch whose answer is estimated above this is cut off mid-JSON (`finish_reason: length`) and unusable, so a caller
        sizes its batches to it - never only to `batch_output_ceiling`, which is None while no allowance is known although
        the per-request cap always applies. It is exactly what `correct` reserves (`_reservation_cap`)."""
        return self._reservation_cap()

    def _salvage_key(self, source_language: str, target_language: str, segment: TranslatableSegment) -> tuple[str, str, str, str]:
        return (source_language, target_language, segment.segment_id, segment.original_text)

    def _salvage_get(self, source_language: str, target_language: str, segment: TranslatableSegment) -> str | None:
        with self._salvage_lock:
            return self._salvaged.get(self._salvage_key(source_language, target_language, segment))

    def _salvage_put(self, source_language: str, target_language: str, segments: TranslationBatch, done: Mapping[str, str]) -> None:
        with self._salvage_lock:
            for segment in segments:
                if segment.segment_id in done:
                    self._salvaged[self._salvage_key(source_language, target_language, segment)] = done[segment.segment_id]
            while len(self._salvaged) > MAX_SALVAGED_LINES:
                self._salvaged.popitem(last=False)

    def _salvage_drop(self, source_language: str, target_language: str, segments: TranslationBatch) -> None:
        with self._salvage_lock:
            for segment in segments:
                self._salvaged.pop(self._salvage_key(source_language, target_language, segment), None)

    def _translate_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
        depth: int,
    ) -> dict[str, str]:
        try:
            # Long canonical IDs must also fit in the JSON completion. Leave
            # room for translated text and JSON rather than spending the whole
            # budget echoing provenance IDs. Split before a predictably large
            # generation, using the same bounded recovery as provider refusals.
            # The size that matters is the wire's: long canonical ids travel as short handles (_wire_segments).
            output_chars = _output_chars(_wire_segments(segments)[0])
            if len(segments) > 1 and output_chars > 2 * self._reservation_cap():
                raise _RequestTooLarge()
            return self._request_batch(source_language, target_language, segments)
        except _RequestTooLarge:
            if len(segments) < 2 or depth >= MAX_TRANSLATION_SPLIT_DEPTH:
                raise TranslationProviderError(
                    "Groq translation request exceeds the model token ceiling.", reason="request_too_large"
                ) from None
            middle = len(segments) // 2
            merged: dict[str, str] = {}
            for half in (segments[:middle], segments[middle:]):
                try:
                    done = self._translate_batch(source_language, target_language, half, depth + 1)
                except TranslationProviderError:
                    # A rate limit (or any stop) part-way: what the earlier halves produced was billed, so it is kept for
                    # the next ask instead of being thrown away with the exception.
                    self._salvage_put(source_language, target_language, segments, merged)
                    raise
                merged.update(done)
            return merged

    def _completion_budget(self, wire: tuple[TranslatableSegment, ...]) -> int:
        """The completion room this batch asks for: what it can need, never more than the configured ceiling.

        A provider admits a request against the room left in an allowance for `prompt + max_completion_tokens`, so a
        fixed reservation (2048) refused a 12-line batch that needed about 500 completion tokens whenever an allowance
        was nearly spent, and the same batch was refused every time it was asked again (2026-10-15 trial). The size is
        the one the batch guard already uses (two characters a token); a reply that still does not fit ends with
        `finish_reason: length` and the batch is halved, as before."""
        cap = self._reservation_cap()
        return min(cap, max(min(MIN_GROQ_MAX_COMPLETION_TOKENS, cap), math.ceil(_output_chars(wire) / 2)))

    def _record(self, started: float, outcome: str, usage: object, error: BaseException | None = None) -> None:
        """Every Groq translation request in the shared AI ledger (ai/audio_telemetry.py): provider, model, the
        provider-reported tokens and the cost from the catalog. A request the provider answered is one row even when
        its batch is then split (its tokens were billed); no text is recorded."""
        from writing_coach.ai.audio_telemetry import record_token_operation

        reported = usage if isinstance(usage, dict) else {}
        listener = _USAGE_SINK.get()
        if listener is not None and outcome == "success" and reported:
            listener(self._model, dict(reported))
        # Every call of this recorder follows `requests.post` (an answer, a refusal, or the post's own failure):
        # the request reached the transport, so it is a billable attempt (PR-MON-6 §8).
        record_token_operation(
            "media_translation", provider=self.engine_id, model=self._model, outcome=outcome,
            latency_ms=int((time.perf_counter() - started) * 1000), usage=reported, error=error,
            billable_attempt=True,
        )

    def _reserve_output(self, tokens: int) -> list[float] | None:
        """Before a request is sent: make room for its reserved output tokens in the model's minute, or refuse it unsent.

        Within a pacing allowance (`translation_pacing`) the wait for room is slept here; otherwise, or when the wait is
        longer than what is left of the allowance, the request is refused as `rate_limited` carrying the exact wait. A
        request refused here reaches no provider, books no tokens, and asks nothing of the allowance (D-218)."""
        if self._otpm.limit is None:
            return None
        for _ in range(3):
            wait = self._otpm.wait_for(tokens, _monotonic())
            if wait <= 0:
                return self._otpm.reserve(tokens, _monotonic())
            budget = _PACING.get()
            if budget is None or wait > budget.remaining:
                raise TranslationProviderError("Groq translation is waiting for its output-token allowance.",
                                               reason="rate_limited", retry_after=math.ceil(wait))
            budget.remaining -= wait
            _pause(wait)
        raise TranslationProviderError("Groq translation is waiting for its output-token allowance.",
                                       reason="rate_limited", retry_after=OTPM_WINDOW_SECONDS + OTPM_MARGIN_SECONDS)

    def _learn_from_refusal(self, response: object, reserved: list[float] | None, asked: float) -> float:
        """A 429 that names the output-tokens-per-minute allowance teaches this process its limit. Groq words it two ways:

        * the minute is full (`Limit N, Used M, Requested R`): the limit and the use are learned, the window is held, and
          the answer is a wait that clears the whole window (never the shorter `retry-after`, which the trial showed
          leaves the window full again);
        * one request is larger than the whole allowance (`Limit N, Requested R`, no `Used`): only the limit is learned.
          Nothing was admitted, so there is no use to sync and no window to hold, and `asked` comes back unchanged: the
          caller asks for less (`batch_output_ceiling` now answers) instead of waiting.

        Any other 429 teaches nothing and also returns `asked`."""
        if reserved is not None:
            self._otpm.release(reserved)   # it was not admitted: it spent nothing of the minute
        refusal = _otpm_refusal(response)
        if refusal is None:
            too_large = _otpm_request_too_large(response)
            if too_large is not None:
                # Only the limit is learned: a request that was not admitted spent nothing of the minute, so there is no
                # `used` to sync and no window to block - the caller asks for less (`batch_output_ceiling` now answers).
                self._otpm.set_limit(too_large[0])
            return asked
        limit, used = refusal
        self._otpm.set_limit(limit)
        now = _monotonic()
        self._otpm.sync_used(used, now)
        wait = max(asked, OTPM_WINDOW_SECONDS + OTPM_MARGIN_SECONDS)
        self._otpm.block_until(now + wait)
        return wait

    def _request_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
    ) -> dict[str, str]:

        wire_segments, canonical_ids = _wire_segments(segments)
        body = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You translate transcript lines for a language-learning product. "
                        "Return JSON only, shaped "
                        '{"translations": [{"segment_id": "...", "translated_meaning": "..."}]}. '
                        "Translate meaning, not word by word. Never add commentary."
                    ),
                },
                {"role": "user", "content": self._prompt(source_language, target_language, wire_segments)},
            ],
            "stream": False,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            # `max_completion_tokens` replaces the deprecated `max_tokens`.
            # Groq reserves prompt + requested completion against one ceiling,
            # so asking for the whole budget left no room for the prompt and
            # returned 413 whenever the bucket was not already full.
            "max_completion_tokens": self._completion_budget(wire_segments),
        }

        reserved = self._reserve_output(body["max_completion_tokens"])
        started = time.perf_counter()
        answered = False
        try:
            response = requests.post(
                self._url,
                json=body,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout,
            )
            self.last_quota = {
                key.lower(): value
                for key, value in response.headers.items()
                if key.lower().startswith("x-ratelimit-")
            }
            if response.status_code == 429 or response.status_code in {401, 403}:
                if response.status_code == 429:
                    # Which allowance was spent (tokens or requests, per minute or per day) is in these headers; they
                    # carry counts and durations only, never a credential (D-211).
                    _logger.warning(
                        "groq translation rate limited: retry_after=%s quota=%s lines=%d detail=%s",
                        response.headers.get("retry-after", ""), self.last_quota, len(segments), _error_detail(response),
                    )
                else:
                    # An auth refusal is the one that used to leave no trace: its status and sentence, never a credential.
                    _logger.warning(
                        "groq translation refused: status=%s lines=%d detail=%s",
                        response.status_code, len(segments), _error_detail(response),
                    )
                asked = _retry_after_seconds(response.headers)
                if response.status_code == 429:
                    asked = self._learn_from_refusal(response, reserved, asked)
                refused = (
                    TranslationProviderError(
                        "Groq translation is rate limited.", reason="rate_limited", retry_after=asked,
                    )
                    if response.status_code == 429
                    else TranslationProviderError("Groq refused the credentials.", reason="provider_auth")
                )
                # A refused call is still a provider call: it reaches the quota telemetry like any other failure.
                self._record(started, "failure", None, refused)
                raise refused
            if response.status_code == 413 and _is_request_too_large(response):
                raise _RequestTooLarge()
            if response.status_code == 400:
                try:
                    error = response.json().get("error", {})
                except (ValueError, AttributeError):
                    error = {}
                # A structured JSON-generation failure can be caused by the
                # completion budget. Retry smaller batches, never another engine.
                if isinstance(error, dict) and error.get("code") == "json_validate_failed":
                    raise _RequestTooLarge()
            response.raise_for_status()
            envelope = response.json()
            answered = True
            self._record(started, "success", envelope.get("usage") if isinstance(envelope, dict) else None)
            if envelope["choices"][0].get("finish_reason") == "length":
                raise _RequestTooLarge()
            content = envelope["choices"][0]["message"]["content"]
            data = json.loads(content)
        except (_RequestTooLarge, TranslationProviderError):
            raise
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            if not answered:
                self._record(started, "failure", None, exc)
            reason = "provider_timeout" if isinstance(exc, requests.Timeout) else "provider_error"
            raise TranslationProviderError("Groq translation is unavailable.", reason=reason) from exc

        items = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise _RequestTooLarge()

        wanted = set(canonical_ids)
        translated: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                raise _RequestTooLarge()
            segment_id = item.get("segment_id")
            meaning = item.get("translated_meaning")
            if (
                not isinstance(segment_id, str)
                or segment_id not in wanted
                or segment_id in translated
                or not isinstance(meaning, str)
                or not meaning.strip()
            ):
                raise _RequestTooLarge()
            translated[segment_id] = meaning.strip()
        if set(translated) != wanted:
            raise _RequestTooLarge()
        return {canonical_ids[key]: value for key, value in translated.items()}


class MediaTranslationService:
    """Translate canonical segments through a configured provider and bounded cache."""

    def __init__(self, provider: TranslationProvider) -> None:
        self._provider = provider
        self._cache: OrderedDict[str, tuple[SegmentTranslation, ...]] = OrderedDict()

    def output_ceiling(self) -> int | None:
        """The provider's per-request output-token ceiling when it has an output-token limit, else None (D-218)."""
        ceiling = getattr(self._provider, "batch_output_ceiling", None)
        return ceiling() if callable(ceiling) else None

    def translate(self, media_object: MediaLearningObject, target_language: str) -> MediaTranslationResult:
        canonical_target = normalize_support_language(target_language)
        transcript = media_object.transcript
        if transcript is None:
            return MediaTranslationResult(media_object, MediaTranslationStatus.TRANSCRIPT_UNAVAILABLE, canonical_target)
        source_language = primary_language(transcript.source_language)
        if source_language == canonical_target:
            return MediaTranslationResult(media_object, MediaTranslationStatus.NOT_REQUIRED, canonical_target)

        batches = build_translation_batches(transcript.segments)
        if batches is None:
            return MediaTranslationResult(media_object, MediaTranslationStatus.TOO_LARGE, canonical_target, reason="too_large")

        cache_key = self._cache_key(source_language, canonical_target, transcript.segments)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return self._ready(media_object, canonical_target, cached, request_count=0)

        generated: dict[str, str] = {}
        request_count = 0
        try:
            for batch in batches:
                request_count += 1
                translated = self._provider.translate_batch(source_language, canonical_target, batch)
                expected = {segment.segment_id for segment in batch}
                if set(translated) != expected or any(not value.strip() for value in translated.values()):
                    return self._unavailable(media_object, canonical_target, MediaTranslationFailureKind.MALFORMED_RESULT, request_count, reason="malformed_result")
                generated.update(translated)
        except TranslationProviderError as exc:
            return self._unavailable(
                media_object, canonical_target, MediaTranslationFailureKind.EXECUTION_UNAVAILABLE, request_count,
                reason=exc.reason, retry_after=exc.retry_after,
            )

        translations = tuple(
            SegmentTranslation(segment.segment_id, canonical_target, generated[segment.segment_id])
            for segment in transcript.segments
        )
        self._cache[cache_key] = translations
        self._cache.move_to_end(cache_key)
        while len(self._cache) > MAX_TRANSLATION_CACHE_ENTRIES:
            self._cache.popitem(last=False)
        return self._ready(media_object, canonical_target, translations, request_count=request_count)

    def _cache_key(self, source: str, target: str, segments: tuple[TranscriptSegment, ...]) -> str:
        digest = hashlib.sha256()
        for segment in segments:
            digest.update(segment.segment_id.encode())
            digest.update(b"\0")
            digest.update(segment.original_text.encode())
            digest.update(b"\0")
        return f"{self._provider.engine_id}:{self._provider.model_version}:{source}:{target}:{digest.hexdigest()}"

    def _ready(self, media_object: MediaLearningObject, target: str, translations: tuple[SegmentTranslation, ...], *, request_count: int) -> MediaTranslationResult:
        try:
            translated_media = MediaLearningObject(
                asset=replace(media_object.asset, translation_available=True),
                transcript=media_object.transcript,
                translations=translations,
            )
        except MediaLearningContractError:
            return self._unavailable(media_object, target, MediaTranslationFailureKind.MALFORMED_RESULT, request_count, reason="malformed_result")
        return MediaTranslationResult(
            translated_media,
            MediaTranslationStatus.READY,
            target,
            MediaTranslationProvenance("local_translation", self._provider.engine_id, self._provider.model_version, request_count),
        )

    def _unavailable(
        self, media_object: MediaLearningObject, target: str, failure: MediaTranslationFailureKind, request_count: int,
        *, reason: str = "provider_error", retry_after: float = 0.0,
    ) -> MediaTranslationResult:
        return MediaTranslationResult(
            media_object,
            MediaTranslationStatus.UNAVAILABLE,
            target,
            MediaTranslationProvenance("local_translation", self._provider.engine_id, self._provider.model_version, request_count),
            failure,
            reason,
            retry_after,
        )


def build_translation_batches(
    segments: tuple[TranslatableSegment, ...], *, max_output_tokens: int | None = None
) -> tuple[TranslationBatch, ...] | None:
    """Cut segments into request batches. With `max_output_tokens` (the provider's `batch_output_ceiling`) each batch also
    fits that much reserved completion room, so one request is one rate-limit decision and a batch either arrives whole or
    not at all (D-218)."""
    batches: list[TranslationBatch] = []
    current: list[TranscriptSegment] = []
    current_chars = 0
    for segment in segments:
        size = len(segment.segment_id) + len(segment.original_text)
        if size > MAX_TRANSLATION_BATCH_CHARS:
            return None
        if current and (len(current) >= MAX_TRANSLATION_BATCH_SEGMENTS or current_chars + size > MAX_TRANSLATION_BATCH_CHARS):
            batches.append(tuple(current))
            current, current_chars = [], 0
        current.append(segment)
        current_chars += size
    if current:
        batches.append(tuple(current))
    if max_output_tokens:
        batches = [group for batch in batches for group in group_by_output_tokens(batch, max_output_tokens)]
    if not batches or len(batches) > MAX_TRANSLATION_BATCHES:
        return None
    return tuple(batches)


_SAFE_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")


def safe_translation_source(provenance: MediaTranslationProvenance | None) -> dict[str, object] | None:
    if provenance is None:
        return None
    provider = provenance.provider if provenance.provider and _SAFE_PROVIDER_ID.fullmatch(provenance.provider) else None
    model = provenance.model if provenance.model and len(provenance.model) <= 80 else None
    return {
        "capability_key": provenance.capability_key,
        "provider": provider,
        "model": model,
        "request_count": provenance.request_count,
    }
