"""On-demand linguistic interaction for the closed shared Media Learning foundation."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from writing_coach.ai.base import AICapabilityError, AIProviderError, AIProviderUnavailable
from writing_coach.ai.platform import generate_structured
from writing_coach.core.request_context import current_language_code
from writing_coach.core.support_languages import (
    UnsupportedSupportLanguage,
    normalize_support_language,
)
from writing_coach.linguistic_annotation import ALLOWED_POS as _SHARED_POS
from writing_coach.linguistic_annotation import annotate as _annotate


router = APIRouter()
contextual_router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])

_ALLOWED_POS = _SHARED_POS
_SUPPORT_LANGUAGE_NAMES = {
    "vi": "Vietnamese",
    "en": "English",
    "zh": "Simplified Chinese",
}
_MAX_ANNOTATIONS = 160


class MediaAnnotateIn(BaseModel):
    """One visible transcript segment to annotate lazily."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1200)
    source_language: str = Field(min_length=2, max_length=32)


class MediaExplainIn(BaseModel):
    """A selected transcript word, phrase, or sentence to explain on demand."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1600)
    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    context: str = Field(default="", max_length=2400)
    # A follow-up is not a new lookup: the learner's question rides along with
    # the selection and the context it is about.
    question: str = Field(default="", max_length=400)

    @field_validator("target_language")
    @classmethod
    def normalize_target_language(cls, value: str) -> str:
        return value.strip().casefold()


class ContextualDictionaryIn(MediaExplainIn):
    """A dictionary request grounded in the exact visible learner context."""

    context: str = Field(min_length=1, max_length=2400)


def _primary_language(value: str) -> str:
    return str(value or "").strip().split("-", 1)[0].casefold()


def _validated_source_language(value: str) -> str:
    requested = _primary_language(value)
    current = _primary_language(current_language_code())
    if requested not in {"en", "zh"} or requested != current:
        raise HTTPException(
            409,
            "Transcript language must match the current learning language.",
        )
    return requested


def _support_language(value: str) -> str:
    try:
        return normalize_support_language(value)
    except UnsupportedSupportLanguage as exc:
        raise HTTPException(422, "Choose a valid support language.") from exc


def _validated_annotations(source: str, raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    output: list[dict[str, Any]] = []
    cursor = 0
    for item in raw[:_MAX_ANNOTATIONS]:
        if not isinstance(item, dict):
            continue
        fragment = str(item.get("fragment") or "")
        pos = str(item.get("pos") or "other").strip().casefold()
        pronunciation = re.sub(r"\s+", " ", str(item.get("pronunciation") or "")).strip()
        lemma = re.sub(r"\s+", " ", str(item.get("lemma") or "")).strip()

        if not fragment or fragment.isspace():
            continue
        if pos not in _ALLOWED_POS:
            pos = "other"

        start = source.find(fragment, cursor)
        if start < 0:
            continue
        end = start + len(fragment)
        output.append(
            {
                "fragment": fragment,
                "start": start,
                "end": end,
                "pos": pos,
                "pronunciation": pronunciation[:120],
                "lemma": lemma[:160],
            }
        )
        cursor = end
    return output


def _local_annotations(language: str, source: str) -> tuple[dict[str, Any], ...]:
    return tuple(_annotate(language, source, max_annotations=_MAX_ANNOTATIONS))


def _run_structured(
    capability_key: str,
    *,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    max_output_tokens: int,
) -> dict[str, Any]:
    try:
        result = generate_structured(
            messages=messages,
            schema=schema,
            max_output_tokens=max_output_tokens,
            temperature=0.0,
            seed=42,
            capability_key=capability_key,
        )
        return result.data if isinstance(result.data, dict) else {}
    except (AIProviderUnavailable, AICapabilityError) as exc:
        raise HTTPException(503, "AI language assistance is not configured right now.") from exc
    except AIProviderError as exc:
        raise HTTPException(502, "AI language assistance returned an invalid response.") from exc


@router.post("/annotate")
def annotate_media_text(payload: MediaAnnotateIn) -> dict[str, Any]:
    """Annotate a visible transcript segment without persisting media/learner state."""
    language = _validated_source_language(payload.source_language)
    source = payload.text.strip()
    if not source:
        raise HTTPException(422, "Transcript text is required.")

    return {
        "source_language": language,
        "text": source,
        "annotations": list(_local_annotations(language, source)),
        "reading_aid": "pinyin" if language == "zh" else None,
        "annotation_version": 1,
        "claim": "interactive_transcript_learning_aid",
    }


# The one vocabulary the product uses to say what kind of problem a piece of
# language has. "Wrong" collapses six different things a learner needs to tell
# apart, so the model must choose one and the UI labels whichever it picks.
USAGE_JUDGEMENTS = (
    "natural",
    "possible_but_unnatural",
    "contextually_inappropriate",
    "wrong_for_intended_meaning",
    "register_mismatch",
    "uncommon_but_legitimate",
    "grammatically_impossible",
)


def _judgement(value: Any) -> str:
    candidate = str(value or "").strip().casefold()
    return candidate if candidate in USAGE_JUDGEMENTS else "natural"


def _examples(raw: Any, *, with_judgement: bool = False) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else ():
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        entry: dict[str, Any] = {
            "text": text[:400],
            "note": str(item.get("note") or "").strip()[:600],
        }
        if with_judgement:
            entry["judgement"] = _judgement(item.get("judgement"))
        items.append(entry)
    return items[:4]


def _explanation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "natural_translation": {"type": "string"},
            "grammar_notes": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string"},
            },
            "vocabulary": {
                "type": "array",
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "properties": {
                        "fragment": {"type": "string"},
                        "meaning": {"type": "string"},
                        "pos": {"type": "string"},
                        "pronunciation": {"type": "string"},
                    },
                    "required": ["fragment", "meaning", "pos", "pronunciation"],
                },
            },
            "usage_note": {"type": "string"},
            "judgement": {"type": "string", "enum": list(USAGE_JUDGEMENTS)},
            "judgement_reason": {"type": "string"},
            "register": {"type": "string"},
            "examples": {
                "type": "array",
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["text", "note"],
                },
            },
            "counter_examples": {
                "type": "array",
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "note": {"type": "string"},
                        "judgement": {"type": "string", "enum": list(USAGE_JUDGEMENTS)},
                    },
                    "required": ["text", "note", "judgement"],
                },
            },
            "follow_ups": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string"},
            },
        },
        "required": [
            "summary",
            "natural_translation",
            "grammar_notes",
            "vocabulary",
            "usage_note",
            "judgement",
            "judgement_reason",
            "register",
            "examples",
            "counter_examples",
            "follow_ups",
        ],
    }


@router.post("/explain")
def explain_media_text(payload: MediaExplainIn) -> dict[str, Any]:
    """Explain selected text, optionally answering the learner's own question.

    One explanation contract serves reading, listening, writing and practice.
    A follow-up is this same call carrying a question, so going deeper never
    loses the selection or the context it came from.
    """
    question = str(payload.question or "").strip()
    language = _validated_source_language(payload.source_language)
    target = _support_language(payload.target_language)
    target_name = _SUPPORT_LANGUAGE_NAMES.get(target, target)
    source_name = "Simplified Chinese" if language == "zh" else "English"
    source = payload.text.strip()
    context = payload.context.strip()

    language_specific = (
        "For Chinese, include contextual tone-mark pinyin for vocabulary and explain useful "
        "particles, measure words, word order, or idiomatic usage when relevant."
        if language == "zh"
        else
        "For English, focus on the actual contextual meaning, grammar, collocation, and register."
    )
    system = (
        "You are an interactive language tutor inside a transcript. "
        f"The learner is studying {source_name}. Explain in {target_name}. "
        "Be concise, concrete, and tied to the supplied context. "
        "Do not invent cultural claims or grammar rules. "
        "Say what kind of usage this is by choosing one judgement: natural; "
        "possible_but_unnatural; contextually_inappropriate; "
        "wrong_for_intended_meaning; register_mismatch; uncommon_but_legitimate; "
        "grammatically_impossible. Wrong alone is not useful to a learner, so "
        "name which of these it is and say why in judgement_reason. "
        "Give examples of the form used well, and counter-examples a learner "
        "would plausibly produce or misread, each labelled with its own "
        "judgement. Counter-examples must be realistic mistakes, not absurd ones. "
        "Offer follow_ups the learner might ask next, phrased as their question. "
        "Never cite a source, rule number, dictionary or corpus you were not "
        "given; explain from the language itself instead. "
        + language_specific
    )
    user = (
        f"SELECTED TEXT:\n{source}\n\n"
        f"CONTEXT:\n{context or source}\n\n"
        "Explain what the selected text means here, why it is phrased this way, "
        "and the most useful vocabulary/grammar to notice."
    )
    if question:
        user = (
            f"SELECTED TEXT:\n{source}\n\n"
            f"CONTEXT:\n{context or source}\n\n"
            f"THE LEARNER ASKS:\n{question}\n\n"
            "Answer their question about the selected text, staying inside this "
            "context and this selection."
        )
    raw = _run_structured(
        "learner_dictionary",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        schema=_explanation_schema(),
        max_output_tokens=1500,
    )
    return {
        "source_language": language,
        "target_language": target,
        "selected_text": source,
        "summary": str(raw.get("summary") or "").strip()[:2400],
        "natural_translation": str(raw.get("natural_translation") or "").strip()[:2400],
        "grammar_notes": [
            str(item).strip()[:600]
            for item in raw.get("grammar_notes", [])
            if str(item).strip()
        ][:5],
        "vocabulary": [
            {
                "fragment": str(item.get("fragment") or "").strip()[:160],
                "meaning": str(item.get("meaning") or "").strip()[:600],
                "pos": str(item.get("pos") or "").strip()[:80],
                "pronunciation": str(item.get("pronunciation") or "").strip()[:120],
            }
            for item in raw.get("vocabulary", [])
            if isinstance(item, dict) and str(item.get("fragment") or "").strip()
        ][:8],
        "usage_note": str(raw.get("usage_note") or "").strip()[:1600],
        "judgement": _judgement(raw.get("judgement")),
        "judgement_reason": str(raw.get("judgement_reason") or "").strip()[:1200],
        "register": str(raw.get("register") or "").strip()[:600],
        "examples": _examples(raw.get("examples")),
        "counter_examples": _examples(raw.get("counter_examples"), with_judgement=True),
        "follow_ups": [
            str(item).strip()[:200]
            for item in raw.get("follow_ups", [])
            if str(item).strip()
        ][:4],
        "question": question,
        "claim": "contextual_ai_explanation",
    }


@contextual_router.post("/contextual")
def contextual_dictionary(payload: ContextualDictionaryIn) -> dict[str, Any]:
    source = payload.text.strip()
    context = payload.context.strip()
    if not source:
        raise HTTPException(422, "Selected text is required.")
    if source.casefold() not in context.casefold():
        raise HTTPException(422, "Selected text must come from the supplied learner context.")
    try:
        result = explain_media_text(payload)
    except HTTPException as exc:
        if exc.status_code not in {502, 503}:
            raise
        return {
            "available": False,
            "source_language": _primary_language(payload.source_language),
            "target_language": payload.target_language.strip().casefold(),
            "selected_text": source,
            "claim": "contextual_dictionary_unavailable",
        }
    if not str(result.get("summary") or "").strip():
        return {
            "available": False,
            "source_language": _primary_language(payload.source_language),
            "target_language": payload.target_language.strip().casefold(),
            "selected_text": source,
            "claim": "contextual_dictionary_unavailable",
        }
    result["available"] = True
    result["claim"] = "contextual_dictionary"
    return result
