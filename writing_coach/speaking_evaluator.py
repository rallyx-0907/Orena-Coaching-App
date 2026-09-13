"""R7 per-take Speaking evaluation contract.

This module deliberately does not call a provider, persist audio, or infer a
learner's proficiency.  It normalizes evidence that already came from the
transient ASR/content-match and pronunciation boundaries into one per-take
shape for a later authenticated Speaking evaluation route.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


class SpeakingEvaluationInvalid(ValueError):
    """Raised when a per-take Speaking evaluation payload is unsafe."""


LANGUAGE_LOCALES = {"en": "en-US", "zh": "zh-CN"}
DIMENSIONS = (
    "transcription_confidence",
    "content_match",
    "pronunciation",
    "fluency",
    "proficiency",
)


def _score(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpeakingEvaluationInvalid(f"{field} must be a number or null.")
    if not math.isfinite(float(value)) or not 0 <= float(value) <= 100:
        raise SpeakingEvaluationInvalid(f"{field} must be between 0 and 100.")
    return round(float(value), 2)


def _text(value: Any, field: str, *, max_chars: int) -> str:
    if not isinstance(value, str):
        raise SpeakingEvaluationInvalid(f"{field} must be text.")
    cleaned = value.strip()
    if len(cleaned) > max_chars:
        raise SpeakingEvaluationInvalid(f"{field} is too long.")
    return cleaned


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(key, default)
    return getattr(source, key, default)


def _content_evidence(content_match: Any) -> tuple[float | None, list[str], list[str]]:
    if isinstance(content_match, Mapping):
        score = content_match.get("content_match", content_match.get("score"))
        missing = content_match.get("missing_tokens", [])
        extra = content_match.get("extra_tokens", [])
    else:
        score, missing, extra = content_match, [], []

    def token_list(value: Any, field: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            raise SpeakingEvaluationInvalid(f"{field} must be a list.")
        return [str(item).strip() for item in value if str(item).strip()]

    normalized_missing = token_list(missing, "missing_tokens")
    normalized_extra = token_list(extra, "extra_tokens")
    return _score(score, "content_match"), normalized_missing[:20], normalized_extra[:20]


def _pronunciation_evidence(pronunciation: Any) -> tuple[dict[str, Any], dict[str, float | None]]:
    if pronunciation is None:
        return {
            "provider": None,
            "score_kind": None,
            "locale": None,
            "accuracy_score": None,
            "completeness_score": None,
            "prosody_score": None,
            "words": [],
        }, {
            "pronunciation": None,
            "fluency": None,
        }

    words: list[dict[str, Any]] = []
    raw_words = _value(pronunciation, "words", ())
    if raw_words is None:
        raw_words = ()
    if not isinstance(raw_words, Sequence) or isinstance(raw_words, (str, bytes, bytearray)):
        raise SpeakingEvaluationInvalid("pronunciation.words must be a list.")
    for raw_word in raw_words[:120]:
        word = _text(_value(raw_word, "word", ""), "pronunciation.words.word", max_chars=120)
        if not word:
            continue
        phonemes: list[dict[str, Any]] = []
        raw_phonemes = _value(raw_word, "phonemes", ()) or ()
        if not isinstance(raw_phonemes, Sequence) or isinstance(raw_phonemes, (str, bytes, bytearray)):
            raise SpeakingEvaluationInvalid("pronunciation.words.phonemes must be a list.")
        for raw_phoneme in raw_phonemes[:80]:
            phoneme = _text(
                _value(raw_phoneme, "phoneme", ""),
                "pronunciation.words.phonemes.phoneme",
                max_chars=40,
            )
            if not phoneme:
                continue
            phonemes.append({
                "phoneme": phoneme,
                "accuracy_score": _score(
                    _value(raw_phoneme, "accuracy_score"),
                    "pronunciation.words.phonemes.accuracy_score",
                ),
            })
        error_type = str(_value(raw_word, "error_type", "None") or "None").strip()[:60]
        if error_type.casefold() == "none":
            error_type = "None"
        words.append({
            "word": word,
            "accuracy_score": _score(
                _value(raw_word, "accuracy_score"),
                "pronunciation.words.accuracy_score",
            ),
            "error_type": error_type,
            "phonemes": phonemes,
        })

    scores = {
        "pronunciation": _score(_value(pronunciation, "pron_score"), "pron_score"),
        "fluency": _score(_value(pronunciation, "fluency_score"), "fluency_score"),
    }
    return {
        "provider": str(_value(pronunciation, "provider", "") or "")[:80] or None,
        "score_kind": str(_value(pronunciation, "score_kind", "") or "")[:40] or None,
        "locale": str(_value(pronunciation, "locale", "") or "")[:40] or None,
        "accuracy_score": _score(_value(pronunciation, "accuracy_score"), "accuracy_score"),
        "completeness_score": _score(
            _value(pronunciation, "completeness_score"), "completeness_score"
        ),
        "prosody_score": _score(_value(pronunciation, "prosody_score"), "prosody_score"),
        "words": words,
    }, scores


def _has_weak_pronunciation_evidence(word: Mapping[str, Any]) -> bool:
    """Return whether a word or one of its phonemes needs another pass."""

    weak_word = (
        word.get("accuracy_score") is not None and word["accuracy_score"] < 80
    ) or str(word.get("error_type", "None")).casefold() != "none"
    weak_phoneme = any(
        isinstance(phoneme, Mapping)
        and phoneme.get("accuracy_score") is not None
        and phoneme["accuracy_score"] < 80
        for phoneme in word.get("phonemes", [])
    )
    return weak_word or weak_phoneme


def build_speaking_evaluation(
    *,
    language: str,
    reference_text: str,
    transcript_text: str,
    content_match: Any = None,
    pronunciation: Any = None,
    transcription_confidence: Any = None,
) -> dict[str, Any]:
    """Return a validated, per-take Speaking evidence envelope.

    ``content_match`` may be the numeric score or the existing deterministic
    matcher object. ``pronunciation`` accepts the provider result dataclass or
    its JSON-shaped mapping. The output intentionally leaves proficiency null.
    """

    normalized_language = str(language or "").strip().casefold()
    if normalized_language not in LANGUAGE_LOCALES:
        raise SpeakingEvaluationInvalid("language must be 'en' or 'zh'.")
    reference = _text(reference_text, "reference_text", max_chars=1200)
    transcript = _text(transcript_text, "transcript_text", max_chars=2400)
    confidence = _score(transcription_confidence, "transcription_confidence")
    match_score, missing_tokens, extra_tokens = _content_evidence(content_match)
    if not reference and (match_score is not None or missing_tokens or extra_tokens):
        raise SpeakingEvaluationInvalid("Content alignment requires reference text.")
    pronunciation_evidence, pronunciation_scores = _pronunciation_evidence(pronunciation)
    synthetic_demo = pronunciation_evidence["score_kind"] == "synthetic_demo"
    pronunciation_source = "synthetic_demo" if synthetic_demo else pronunciation_evidence["provider"]

    dimensions = {
        "transcription_confidence": confidence,
        "content_match": match_score,
        "pronunciation": pronunciation_scores["pronunciation"],
        "fluency": pronunciation_scores["fluency"],
        # A per-take pronunciation result is not a proficiency estimate.
        "proficiency": None,
    }
    provenance = {
        "transcription_confidence": "speech_asr" if confidence is not None else None,
        # Free expression has no line to match, which is not the same as an
        # alignment that was attempted and failed. Saying "not measured" there
        # would describe a missing measurement rather than a dimension that
        # does not apply to what the learner was asked to do.
        "content_match": (
            "deterministic_reference_alignment"
            if match_score is not None
            else "not_applicable"
            if not reference
            else None
        ),
        "pronunciation": pronunciation_source if pronunciation_scores["pronunciation"] is not None else None,
        "fluency": pronunciation_source if pronunciation_scores["fluency"] is not None else None,
        "proficiency": "not_assessed",
    }

    highlights: list[str] = []
    next_steps: list[dict[str, Any]] = []
    if (pronunciation_evidence["accuracy_score"] or 0) >= 85:
        highlights.append("clear_pronunciation")
    if (pronunciation_evidence["completeness_score"] or 0) >= 90:
        highlights.append("complete_line")
    if (pronunciation_scores["fluency"] or 0) >= 80:
        highlights.append("steady_pace")
    if (match_score or 0) >= 85:
        highlights.append("on_source_line")

    weak_words = [
        item["word"]
        for item in pronunciation_evidence["words"]
        if _has_weak_pronunciation_evidence(item)
    ][:4]
    if weak_words:
        next_steps.append({"kind": "focus_words", "words": weak_words})
    if missing_tokens:
        next_steps.append({"kind": "missing_tokens", "words": missing_tokens[:5]})
    if pronunciation_scores["fluency"] is not None and pronunciation_scores["fluency"] < 80:
        next_steps.append({"kind": "fluency", "words": []})
    if (
        pronunciation_evidence["completeness_score"] is not None
        and pronunciation_evidence["completeness_score"] < 90
    ):
        next_steps.append({"kind": "complete_line", "words": []})

    return {
        "schema_version": 1,
        "language": normalized_language,
        "locale": LANGUAGE_LOCALES[normalized_language],
        "dimensions": dimensions,
        "provenance": provenance,
        "evidence": {
            "reference_text": reference,
            "recognized_text": transcript,
            "content": {
                "missing_tokens": missing_tokens,
                "extra_tokens": extra_tokens,
            },
            "pronunciation": pronunciation_evidence,
            "synthetic_demo": synthetic_demo,
        },
        "highlights": highlights,
        "next_steps": next_steps,
    }


__all__ = [
    "DIMENSIONS",
    "LANGUAGE_LOCALES",
    "SpeakingEvaluationInvalid",
    "build_speaking_evaluation",
]
