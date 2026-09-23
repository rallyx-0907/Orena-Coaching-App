"""HTTP boundary for speech ASR."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import math
import time
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from writing_coach.core.errors import orena_http_error
from writing_coach.core.request_context import current_language_code

from writing_coach.speech_pronunciation import (
    SpeechPronunciationConversionFailed,
    SpeechPronunciationMalformed,
    SpeechPronunciationNoSpeech,
    SpeechPronunciationPayloadTooLarge,
    SpeechPronunciationProvider,
    SpeechPronunciationRequestFailed,
    SpeechPronunciationTimedOut,
)

from writing_coach.speech_asr import (
    SpeechAsrMalformed,
    SpeechAsrPayloadTooLarge,
    SpeechAsrProvider,
    SpeechAsrRequestFailed,
    SpeechAsrTimedOut,
)
from writing_coach.speaking_evaluator import (
    SpeakingEvaluationInvalid,
    build_speaking_evaluation,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/speech", tags=["speech"])
_speech_asr_provider: SpeechAsrProvider | None = None
_speech_pronunciation_provider: SpeechPronunciationProvider | None = None
_speaking_attempt_repository: Any = None


def configure_speech_asr(provider: SpeechAsrProvider | None) -> None:
    global _speech_asr_provider
    _speech_asr_provider = provider


def configure_speech_pronunciation(provider: SpeechPronunciationProvider | None) -> None:
    global _speech_pronunciation_provider
    _speech_pronunciation_provider = provider


def configure_speaking_attempt_repository(repository: Any) -> None:
    """Attach the scoped persistence boundary for completed Speaking takes."""
    global _speaking_attempt_repository
    _speaking_attempt_repository = repository


def _provider() -> SpeechAsrProvider:
    if _speech_asr_provider is None:
        raise orena_http_error(
            503,
            "speech_asr_unconfigured",
            "Speech recognition is not configured.",
        )
    return _speech_asr_provider


def _pronunciation_provider() -> SpeechPronunciationProvider:
    if _speech_pronunciation_provider is None:
        raise orena_http_error(
            503,
            "pronunciation_unconfigured",
            "Pronunciation assessment is not configured.",
        )
    return _speech_pronunciation_provider


_UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
_DEFAULT_ASR_MAX_BYTES = 24 * 1024 * 1024


class SpeakingEvaluationIn(BaseModel):
    """Transient evidence envelope for the internal R7 evaluator boundary."""

    # Keep raw values until build_speaking_evaluation so every invalid field,
    # including over-limit text, uses the canonical speech error envelope.
    language: Any = ""
    reference_text: Any = ""
    transcript_text: Any = ""
    content_match: Any = None
    pronunciation: Any = None
    transcription_confidence: Any = None


class SpeakingAttemptIn(BaseModel):
    """Client envelope for one already-completed, audio-free evaluation."""

    language: Any = ""
    take_id: Any = ""
    asset_id: Any = ""
    segment_id: Any = ""
    reference_text: Any = ""
    transcript_text: Any = ""
    evaluation: Any = None


def _attempt_text(value: Any, field: str, *, max_chars: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise SpeakingEvaluationInvalid(f"{field} must be text.")
    result = value.strip()
    if required and not result:
        raise SpeakingEvaluationInvalid(f"{field} must not be empty.")
    if len(result) > max_chars:
        raise SpeakingEvaluationInvalid(f"{field} is too long.")
    return result


def _normalize_speaking_attempt(payload: SpeakingAttemptIn) -> dict[str, Any]:
    language = _attempt_text(payload.language, "language", max_chars=8).casefold()
    if language not in {"en", "zh"}:
        raise SpeakingEvaluationInvalid("language must be 'en' or 'zh'.")
    scoped_language = current_language_code().strip().casefold()
    if scoped_language in {"en", "zh"} and language != scoped_language:
        raise SpeakingEvaluationInvalid("language does not match the learner scope.")
    take_id = _attempt_text(payload.take_id, "take_id", max_chars=120)
    asset_id = _attempt_text(payload.asset_id, "asset_id", max_chars=255, required=False)
    segment_id = _attempt_text(payload.segment_id, "segment_id", max_chars=255)
    # Free expression has no reference line. It uses the same audio-free
    # evidence record, with alignment explicitly unmeasured; no new schema.
    reference = _attempt_text(payload.reference_text, "reference_text", max_chars=1200, required=False)
    transcript = _attempt_text(payload.transcript_text, "transcript_text", max_chars=2400)
    evaluation = payload.evaluation
    if not isinstance(evaluation, dict):
        raise SpeakingEvaluationInvalid("evaluation must be an object.")
    dimensions = evaluation.get("dimensions")
    provenance = evaluation.get("provenance")
    evidence = evaluation.get("evidence")
    if not isinstance(dimensions, dict) or not isinstance(provenance, dict) or not isinstance(evidence, dict):
        raise SpeakingEvaluationInvalid("evaluation envelope is incomplete.")
    if dimensions.get("proficiency") is not None:
        raise SpeakingEvaluationInvalid("proficiency is not persisted by Speaking.")
    bounded_dimensions: dict[str, float | None] = {}
    for key in ("transcription_confidence", "content_match", "pronunciation", "fluency"):
        value = dimensions.get(key)
        if value is None:
            bounded_dimensions[key] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)) or not 0 <= float(value) <= 100:
            raise SpeakingEvaluationInvalid(f"dimensions.{key} is invalid.")
        bounded_dimensions[key] = round(float(value), 2)
    def text_list(value: Any, field: str, limit: int) -> list[str]:
        if not isinstance(value, list):
            raise SpeakingEvaluationInvalid(f"{field} must be a list.")
        result: list[str] = []
        for item in value[:limit]:
            if not isinstance(item, str):
                raise SpeakingEvaluationInvalid(f"{field} must contain text.")
            result.append(_attempt_text(item, field, max_chars=160))
        return result

    def score(value: Any, field: str) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SpeakingEvaluationInvalid(f"{field} is invalid.")
        if not math.isfinite(float(value)) or not 0 <= float(value) <= 100:
            raise SpeakingEvaluationInvalid(f"{field} is invalid.")
        return round(float(value), 2)

    if set(evidence) - {"reference_text", "recognized_text", "content", "pronunciation", "synthetic_demo", "highlights", "next_steps"}:
        raise SpeakingEvaluationInvalid("evaluation evidence contains unsupported fields.")
    normalized_evidence: dict[str, Any] = {}
    for key in ("reference_text", "recognized_text"):
        if key in evidence:
            normalized_evidence[key] = _attempt_text(evidence[key], f"evidence.{key}", max_chars=2400, required=key != "reference_text")
    content = evidence.get("content")
    if content is not None:
        if not isinstance(content, dict) or set(content) - {"missing_tokens", "extra_tokens"}:
            raise SpeakingEvaluationInvalid("evidence.content is invalid.")
        normalized_evidence["content"] = {
            "missing_tokens": text_list(content.get("missing_tokens", []), "evidence.content.missing_tokens", 20),
            "extra_tokens": text_list(content.get("extra_tokens", []), "evidence.content.extra_tokens", 20),
        }
    if not reference and (bounded_dimensions.get("content_match") is not None or
                          (normalized_evidence.get("content") or {}).get("missing_tokens") or
                          (normalized_evidence.get("content") or {}).get("extra_tokens")):
        raise SpeakingEvaluationInvalid("Content alignment requires reference text.")
    pronunciation = evidence.get("pronunciation")
    if pronunciation is not None:
        allowed_pronunciation = {"provider", "score_kind", "locale", "accuracy_score", "completeness_score", "prosody_score", "words"}
        if not isinstance(pronunciation, dict) or set(pronunciation) - allowed_pronunciation:
            raise SpeakingEvaluationInvalid("evidence.pronunciation is invalid.")
        normalized_pronunciation: dict[str, Any] = {}
        for key, max_chars in (("provider", 80), ("score_kind", 40), ("locale", 40)):
            if key in pronunciation:
                value = pronunciation[key]
                if value is not None and not isinstance(value, str):
                    raise SpeakingEvaluationInvalid(f"evidence.pronunciation.{key} is invalid.")
                normalized_pronunciation[key] = None if value is None else value[:max_chars]
        for key in ("accuracy_score", "completeness_score", "prosody_score"):
            if key in pronunciation:
                normalized_pronunciation[key] = score(pronunciation[key], f"evidence.pronunciation.{key}")
        words = pronunciation.get("words", [])
        if not isinstance(words, list):
            raise SpeakingEvaluationInvalid("evidence.pronunciation.words is invalid.")
        normalized_words: list[dict[str, Any]] = []
        for word in words[:120]:
            if not isinstance(word, dict) or set(word) - {"word", "accuracy_score", "error_type", "phonemes"}:
                raise SpeakingEvaluationInvalid("evidence.pronunciation.words is invalid.")
            word_text = _attempt_text(word.get("word", ""), "evidence.pronunciation.words.word", max_chars=120)
            phonemes = word.get("phonemes", [])
            if not isinstance(phonemes, list):
                raise SpeakingEvaluationInvalid("evidence.pronunciation.words.phonemes is invalid.")
            normalized_phonemes: list[dict[str, Any]] = []
            for phoneme in phonemes[:80]:
                if not isinstance(phoneme, dict) or set(phoneme) - {"phoneme", "accuracy_score"}:
                    raise SpeakingEvaluationInvalid("evidence.pronunciation.words.phonemes is invalid.")
                normalized_phonemes.append({
                    "phoneme": _attempt_text(phoneme.get("phoneme", ""), "evidence.pronunciation.words.phonemes.phoneme", max_chars=40),
                    "accuracy_score": score(phoneme.get("accuracy_score"), "evidence.pronunciation.words.phonemes.accuracy_score"),
                })
            error_type = word.get("error_type", "None")
            if not isinstance(error_type, str):
                raise SpeakingEvaluationInvalid("evidence.pronunciation.words.error_type is invalid.")
            normalized_words.append({
                "word": word_text,
                "accuracy_score": score(word.get("accuracy_score"), "evidence.pronunciation.words.accuracy_score"),
                "error_type": error_type[:60],
                "phonemes": normalized_phonemes,
            })
        normalized_pronunciation["words"] = normalized_words
        normalized_evidence["pronunciation"] = normalized_pronunciation
    if "synthetic_demo" in evidence:
        if not isinstance(evidence["synthetic_demo"], bool):
            raise SpeakingEvaluationInvalid("evidence.synthetic_demo is invalid.")
        normalized_evidence["synthetic_demo"] = evidence["synthetic_demo"]
    if "highlights" in evidence:
        normalized_evidence["highlights"] = text_list(evidence["highlights"], "evidence.highlights", 20)
    if "next_steps" in evidence:
        steps = evidence["next_steps"]
        if not isinstance(steps, list):
            raise SpeakingEvaluationInvalid("evidence.next_steps is invalid.")
        normalized_steps: list[dict[str, Any]] = []
        for step in steps[:20]:
            if not isinstance(step, dict) or set(step) - {"kind", "words"} or not isinstance(step.get("kind"), str):
                raise SpeakingEvaluationInvalid("evidence.next_steps is invalid.")
            normalized_steps.append({"kind": step["kind"][:80], "words": text_list(step.get("words", []), "evidence.next_steps.words", 20)})
        normalized_evidence["next_steps"] = normalized_steps
    allowed_provenance = {
        "transcription_confidence", "content_match", "pronunciation", "fluency", "proficiency",
    }
    if set(provenance) - allowed_provenance:
        raise SpeakingEvaluationInvalid("evaluation provenance contains unsupported fields.")
    safe_provenance: dict[str, str | None] = {}
    for key in allowed_provenance:
        if key not in provenance:
            continue
        value = provenance[key]
        if value is not None and not isinstance(value, str):
            raise SpeakingEvaluationInvalid(f"provenance.{key} is invalid.")
        safe_provenance[key] = None if value is None else value[:120]
    try:
        encoded_evidence = json.dumps(normalized_evidence, ensure_ascii=False, separators=(",", ":"))
        encoded_provenance = json.dumps(safe_provenance, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SpeakingEvaluationInvalid("evaluation evidence is not JSON-safe.") from exc
    if len(encoded_evidence) > 100_000 or len(encoded_provenance) > 8_000:
        raise SpeakingEvaluationInvalid("evaluation evidence is too large.")
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "language": language,
        "take_id": take_id,
        "asset_id": asset_id,
        "segment_id": segment_id,
        "reference_text": reference,
        "transcript_text": transcript,
        "dimensions": bounded_dimensions,
        "provenance": safe_provenance,
        "evidence": normalized_evidence,
    }


async def _read_upload_limited(file: UploadFile, *, max_bytes: int) -> bytes:
    if max_bytes <= 0:
        raise SpeechAsrPayloadTooLarge()
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = max_bytes - total + 1
        chunk = await file.read(min(_UPLOAD_READ_CHUNK_BYTES, remaining))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise SpeechAsrPayloadTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


@router.get("/status")
def speech_status() -> dict[str, Any]:
    # Pronunciation is its own capability: a room that scores a line asks this
    # before inviting a take. Which provider answers stays infrastructure.
    pronunciation = {"configured": _speech_pronunciation_provider is not None}
    provider = _speech_asr_provider
    if provider is None:
        return {"configured": False, "provider": None, "model": None, "pronunciation": pronunciation}
    return {
        "configured": True,
        "provider": getattr(provider, "provider_id", "unknown"),
        "model": getattr(provider, "model", None),
        "pronunciation": pronunciation,
    }


@router.post("/transcribe")
async def transcribe_speech(
    file: UploadFile = File(...),
    language: str = Form(default=""),
) -> dict[str, Any]:
    normalized_language = language.strip().casefold() or None
    if normalized_language is not None and normalized_language not in {"en", "zh"}:
        raise orena_http_error(
            422,
            "speech_asr_invalid_language",
            "Unsupported speech language.",
        )

    provider = _provider()
    max_bytes = int(getattr(provider, "max_bytes", _DEFAULT_ASR_MAX_BYTES))
    try:
        data = await _read_upload_limited(file, max_bytes=max_bytes)
        result = provider.transcribe_bytes(
            data,
            filename=file.filename or "recording.webm",
            content_type=file.content_type or "application/octet-stream",
            language=normalized_language,
        )
    except SpeechAsrPayloadTooLarge as exc:
        raise orena_http_error(
            413,
            "speech_asr_payload_too_large",
            "Audio recording is too large.",
        ) from exc
    except SpeechAsrTimedOut as exc:
        raise orena_http_error(
            504,
            "speech_asr_timeout",
            "Speech transcription timed out.",
            retryable=True,
        ) from exc
    except SpeechAsrMalformed as exc:
        raise orena_http_error(
            502,
            "speech_asr_provider_malformed",
            "Speech provider returned an unusable transcript.",
        ) from exc
    except SpeechAsrRequestFailed as exc:
        provider_status = getattr(exc, "status_code", None)
        category = {
            400: "speech_asr_invalid_request",
            401: "speech_asr_auth",
            403: "speech_asr_forbidden",
            422: "speech_asr_unprocessable_audio",
            429: "speech_asr_rate_limited",
            498: "speech_asr_capacity",
        }.get(provider_status, "speech_asr_provider_failure")
        public_message = {
            "speech_asr_invalid_request": "The speech provider rejected the audio request.",
            "speech_asr_auth": "Speech recognition credentials were rejected.",
            "speech_asr_forbidden": "Speech recognition is not permitted for this API key.",
            "speech_asr_unprocessable_audio": "The speech provider could not process this audio.",
            "speech_asr_rate_limited": "Speech recognition rate limit reached. Try again shortly.",
            "speech_asr_capacity": "Speech recognition capacity is temporarily unavailable.",
        }.get(category, "Speech recognition provider failed.")
        raise orena_http_error(
            502,
            category,
            public_message,
            context={"provider_status": provider_status},
        ) from exc

    return {
        "provider": result.provider,
        "model": result.model,
        "language": result.language,
        "text": result.text,
        "segments": [
            {"start_ms": x.start_ms, "end_ms": x.end_ms, "text": x.text}
            for x in result.segments
        ],
        "words": [
            {"start_ms": x.start_ms, "end_ms": x.end_ms, "word": x.word}
            for x in result.words
        ],
    }


@router.post("/evaluation")
def evaluate_speaking(payload: SpeakingEvaluationIn) -> dict[str, Any]:
    """Normalize one transient Speaking take without persisting audio or scores."""

    values = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    try:
        return build_speaking_evaluation(**values)
    except SpeakingEvaluationInvalid as exc:
        raise orena_http_error(
            422,
            "speaking_evaluation_invalid",
            str(exc),
        ) from exc


@router.post("/attempts")
def save_speaking_attempt(payload: SpeakingAttemptIn) -> dict[str, Any]:
    """Persist normalized evaluator evidence without accepting raw audio."""
    if _speaking_attempt_repository is None:
        raise orena_http_error(
            503,
            "speaking_attempts_unconfigured",
            "Speaking history is not configured on this environment.",
        )
    try:
        values = _normalize_speaking_attempt(payload)
        saved = _speaking_attempt_repository.create_speaking_attempt_record(values)
    except SpeakingEvaluationInvalid as exc:
        raise orena_http_error(422, "speaking_attempt_invalid", str(exc)) from exc
    return {"item": saved, "progress": _speaking_attempt_repository.speaking_progress()}


@router.get("/attempts")
def list_speaking_attempts(
    limit: int = 20,
    asset_id: str | None = None,
    segment_id: str | None = None,
) -> dict[str, Any]:
    if _speaking_attempt_repository is None:
        raise orena_http_error(
            503,
            "speaking_attempts_unconfigured",
            "Speaking history is not configured on this environment.",
        )
    bounded_limit = max(1, min(int(limit), 100))
    scoped_asset = asset_id.strip() if isinstance(asset_id, str) and asset_id.strip() else None
    scoped_segment = segment_id.strip() if isinstance(segment_id, str) and segment_id.strip() else None
    if scoped_asset is None and scoped_segment is None:
        items = _speaking_attempt_repository.list_speaking_attempt_records(bounded_limit)
    else:
        items = _speaking_attempt_repository.list_speaking_attempt_records(
            bounded_limit,
            asset_id=scoped_asset,
            segment_id=scoped_segment,
        )
    return {
        "items": items,
        "progress": _speaking_attempt_repository.speaking_progress(),
    }

_DEFAULT_PRONUNCIATION_MAX_BYTES = 8 * 1024 * 1024


async def _read_pronunciation_upload_limited(
    file: UploadFile,
    *,
    max_bytes: int,
) -> bytes:
    if max_bytes <= 0:
        raise SpeechPronunciationPayloadTooLarge()
    chunks: list[bytes] = []
    total = 0
    while True:
        remaining = max_bytes - total + 1
        chunk = await file.read(min(_UPLOAD_READ_CHUNK_BYTES, remaining))
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise SpeechPronunciationPayloadTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/pronunciation")
async def assess_pronunciation(
    file: UploadFile = File(...),
    language: str = Form(default=""),
    reference_text: str = Form(default=""),
    mode: str = Form(default="scripted"),
) -> dict[str, Any]:
    normalized_language = language.strip().casefold()
    if normalized_language not in {"en", "zh"}:
        raise orena_http_error(
            422,
            "pronunciation_invalid_language",
            "Unsupported pronunciation language.",
        )
    normalized_mode = mode.strip().casefold() or "scripted"
    if normalized_mode not in {"scripted", "unscripted"}:
        raise orena_http_error(422, "pronunciation_invalid_mode", "Unsupported pronunciation mode.")
    unscripted = normalized_mode == "unscripted"

    provider = _pronunciation_provider()
    # Free speech (free talk) is assessed with no reference line.
    reference = "" if unscripted else reference_text.strip()
    max_reference_chars = int(getattr(provider, "max_reference_chars", 1200))
    if not unscripted and (not reference or len(reference) > max_reference_chars):
        raise orena_http_error(
            422,
            "pronunciation_reference_invalid",
            "Pronunciation reference text is invalid.",
        )

    max_bytes = int(getattr(provider, "max_bytes", _DEFAULT_PRONUNCIATION_MAX_BYTES))
    provider_id = str(getattr(provider, "provider_id", "unknown"))
    started = time.monotonic()
    outcome = "error"
    size = 0
    try:
        try:
            data = await _read_pronunciation_upload_limited(file, max_bytes=max_bytes)
        except SpeechPronunciationPayloadTooLarge as exc:
            raise orena_http_error(
                413,
                "pronunciation_payload_too_large",
                "Audio recording is too large.",
                context={"max_bytes": max_bytes},
            ) from exc
        size = len(data)
        if not data:
            raise orena_http_error(
                422,
                "pronunciation_audio_empty",
                "The recording is empty.",
            )
        result = _assess(provider, data, file, normalized_language, reference, unscripted)
        outcome = result.score_kind
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        outcome = str(detail.get("category") or outcome)
        raise
    finally:
        latency_ms = int(round((time.monotonic() - started) * 1000))
        # Operations only: never the audio, the line, a key or a provider message.
        logger.info(
            "pronunciation assessment provider=%s language=%s outcome=%s bytes=%d latency_ms=%d",
            provider_id,
            normalized_language,
            outcome,
            size,
            latency_ms,
        )

    return {
        "provider": result.provider,
        "score_kind": result.score_kind,
        "mode": getattr(result, "mode", "scripted"),
        "language": normalized_language,
        "locale": result.locale,
        "reference_text": reference,
        "recognized_text": result.recognized_text,
        "pron_score": result.pron_score,
        "accuracy_score": result.accuracy_score,
        "fluency_score": result.fluency_score,
        "completeness_score": result.completeness_score,
        "prosody_score": result.prosody_score,
        "words": [
            {
                "word": word.word,
                "accuracy_score": word.accuracy_score,
                "error_type": word.error_type,
                "offset_ms": word.offset_ms,
                "duration_ms": word.duration_ms,
                "syllables": [
                    {"syllable": syllable.syllable, "accuracy_score": syllable.accuracy_score}
                    for syllable in word.syllables
                ],
                "phonemes": [
                    {
                        "phoneme": phoneme.phoneme,
                        "accuracy_score": phoneme.accuracy_score,
                    }
                    for phoneme in word.phonemes
                ],
            }
            for word in result.words
        ],
        "latency_ms": latency_ms,
    }


def _assess(
    provider: SpeechPronunciationProvider,
    data: bytes,
    file: UploadFile,
    language: str,
    reference: str,
    unscripted: bool = False,
) -> Any:
    """Call the provider and turn each way it can fail into a learner-safe error.

    No speech is the learner's outcome (say it again), not a provider failure;
    everything else is the service's, and says so without provider detail."""
    try:
        return provider.assess_bytes(
            data,
            filename=file.filename or "recording.webm",
            content_type=file.content_type or "application/octet-stream",
            language=language,
            reference_text=reference,
            unscripted=unscripted,
        )
    except SpeechPronunciationPayloadTooLarge as exc:
        raise orena_http_error(
            413,
            "pronunciation_payload_too_large",
            "Audio recording is too large.",
        ) from exc
    except SpeechPronunciationNoSpeech as exc:
        raise orena_http_error(
            422,
            "pronunciation_no_speech",
            "No speech was heard in the recording.",
        ) from exc
    except SpeechPronunciationTimedOut as exc:
        raise orena_http_error(
            504,
            "pronunciation_timeout",
            "Pronunciation assessment timed out.",
            retryable=True,
        ) from exc
    except SpeechPronunciationConversionFailed as exc:
        raise orena_http_error(
            422,
            "pronunciation_audio_unsupported",
            "The recorded audio could not be prepared for pronunciation assessment.",
        ) from exc
    except SpeechPronunciationMalformed as exc:
        raise orena_http_error(
            502,
            "pronunciation_provider_malformed",
            "Pronunciation provider returned an unusable result.",
        ) from exc
    except SpeechPronunciationRequestFailed as exc:
        provider_status = getattr(exc, "status_code", None)
        category = {
            400: "pronunciation_invalid_request",
            401: "pronunciation_auth",
            403: "pronunciation_forbidden",
            429: "pronunciation_rate_limited",
        }.get(provider_status, "pronunciation_provider_failure")
        public_message = {
            "pronunciation_invalid_request": "The pronunciation provider rejected this request.",
            "pronunciation_auth": "Pronunciation credentials were rejected.",
            "pronunciation_forbidden": "Pronunciation assessment is not permitted for this resource.",
            "pronunciation_rate_limited": "Pronunciation assessment rate limit reached. Try again shortly.",
        }.get(category, "Pronunciation assessment provider failed.")
        raise orena_http_error(
            502,
            category,
            public_message,
            retryable=category in {"pronunciation_rate_limited", "pronunciation_provider_failure"},
            context={"provider_status": provider_status},
        ) from exc
