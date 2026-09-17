"""Provider-neutral, cached shared-media translation."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, replace
from enum import StrEnum
import hashlib
import json
import os
import re
from collections.abc import Mapping
from typing import Protocol

import requests

from writing_coach.core.support_languages import support_language, normalize_support_language
from writing_coach.media_ingestion import primary_language
from writing_coach.media_learning import (
    MediaLearningContractError,
    MediaLearningObject,
    SegmentTranslation,
    TranscriptSegment,
)

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


class _RequestTooLarge(Exception):
    """The provider refused this request for its size, not its timing."""


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


class TranslationProviderError(RuntimeError):
    pass


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

    def __init__(self, base_url: str, *, timeout_seconds: float = 90.0) -> None:
        self._url = base_url.rstrip("/") + "/translate"
        self._timeout = timeout_seconds

    def translate_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
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
            response = requests.post(self._url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise TranslationProviderError("Local translation is unavailable.") from exc
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
    ) -> None:
        self._api_key = str(api_key or "").strip()
        self._model = str(model or "").strip()
        self._url = str(base_url or "").rstrip("/") + "/chat/completions"
        self._timeout = timeout_seconds
        self.model_version = self._model
        self._max_completion_tokens = resolve_max_completion_tokens(max_completion_tokens)
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
            raise TranslationProviderError("Groq translation is not configured.")
        return self._translate_batch(source_language, target_language, segments, depth=0)

    def _translate_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
        depth: int,
    ) -> dict[str, str]:
        try:
            return self._request_batch(source_language, target_language, segments)
        except _RequestTooLarge:
            if len(segments) < 2 or depth >= MAX_TRANSLATION_SPLIT_DEPTH:
                raise TranslationProviderError(
                    "Groq translation request exceeds the model token ceiling."
                ) from None
            middle = len(segments) // 2
            merged: dict[str, str] = {}
            for half in (segments[:middle], segments[middle:]):
                merged.update(
                    self._translate_batch(source_language, target_language, half, depth + 1)
                )
            return merged

    def _request_batch(
        self,
        source_language: str,
        target_language: str,
        segments: TranslationBatch,
    ) -> dict[str, str]:

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
                {"role": "user", "content": self._prompt(source_language, target_language, segments)},
            ],
            "stream": False,
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            # `max_completion_tokens` replaces the deprecated `max_tokens`.
            # Groq reserves prompt + requested completion against one ceiling,
            # so asking for the whole budget left no room for the prompt and
            # returned 413 whenever the bucket was not already full.
            "max_completion_tokens": self._max_completion_tokens,
        }

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
            if response.status_code == 413 and _is_request_too_large(response):
                raise _RequestTooLarge()
            response.raise_for_status()
            envelope = response.json()
            content = envelope["choices"][0]["message"]["content"]
            data = json.loads(content)
        except _RequestTooLarge:
            raise
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise TranslationProviderError("Groq translation is unavailable.") from exc

        items = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(items, list):
            raise TranslationProviderError("Groq translation returned invalid data.")

        wanted = {segment.segment_id for segment in segments}
        translated: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                raise TranslationProviderError("Groq translation returned invalid data.")
            segment_id = item.get("segment_id")
            meaning = item.get("translated_meaning")
            if (
                not isinstance(segment_id, str)
                or segment_id not in wanted
                or segment_id in translated
                or not isinstance(meaning, str)
                or not meaning.strip()
            ):
                raise TranslationProviderError("Groq translation returned invalid data.")
            translated[segment_id] = meaning.strip()
        return translated


class MediaTranslationService:
    """Translate canonical segments through a configured provider and bounded cache."""

    def __init__(self, provider: TranslationProvider) -> None:
        self._provider = provider
        self._cache: OrderedDict[str, tuple[SegmentTranslation, ...]] = OrderedDict()

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
            return MediaTranslationResult(media_object, MediaTranslationStatus.TOO_LARGE, canonical_target)

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
                    return self._unavailable(media_object, canonical_target, MediaTranslationFailureKind.MALFORMED_RESULT, request_count)
                generated.update(translated)
        except TranslationProviderError:
            return self._unavailable(media_object, canonical_target, MediaTranslationFailureKind.EXECUTION_UNAVAILABLE, request_count)

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
            return self._unavailable(media_object, target, MediaTranslationFailureKind.MALFORMED_RESULT, request_count)
        return MediaTranslationResult(
            translated_media,
            MediaTranslationStatus.READY,
            target,
            MediaTranslationProvenance("local_translation", self._provider.engine_id, self._provider.model_version, request_count),
        )

    def _unavailable(self, media_object: MediaLearningObject, target: str, failure: MediaTranslationFailureKind, request_count: int) -> MediaTranslationResult:
        return MediaTranslationResult(
            media_object,
            MediaTranslationStatus.UNAVAILABLE,
            target,
            MediaTranslationProvenance("local_translation", self._provider.engine_id, self._provider.model_version, request_count),
            failure,
        )


def build_translation_batches(segments: tuple[TranslatableSegment, ...]) -> tuple[TranslationBatch, ...] | None:
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
