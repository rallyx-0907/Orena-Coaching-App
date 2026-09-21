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
from writing_coach.conversation import ConversationIn, respond as conversation_reply


router = APIRouter()
contextual_router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])


@contextual_router.post('/conversation-turn')
def continue_conversation(payload: ConversationIn):
    return conversation_reply(payload, language=_validated_source_language(payload.source_language),
                              support=_support_language(payload.target_language), generate=_run_structured)

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


class SpokenResponseIn(BaseModel):
    """A transcribed spoken response, and the situation it answered."""

    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(min_length=1, max_length=2400)
    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    # What the learner was asked to do. Without it, coaching has to guess at the
    # task and ends up marking ordinary choices as omissions.
    situation: str = Field(default="", max_length=1200)

    @field_validator("target_language")
    @classmethod
    def normalize_spoken_target(cls, value: str) -> str:
        return value.strip().casefold()


class RegisterExploreIn(BaseModel):
    """One meaning, asked for across the registers a learner needs to tell apart."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2400)
    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    # What the learner is writing for. It steers which registers are worth
    # contrasting; a lab report and a message to a landlord are not the same
    # kind of formal.
    situation: str = Field(default="", max_length=240)

    @field_validator("target_language")
    @classmethod
    def normalize_register_target(cls, value: str) -> str:
        return value.strip().casefold()


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


# The roles a sentence's parts can play in the Quick Sheet (SentenceSheet.json).
# Deliberately few and language-neutral: an object or a modifier that is not one
# of the first three is a complement.
STRUCTURE_ROLES = ("adverbial", "verb", "subject", "complement")


def _contrast(raw: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for item in raw if isinstance(raw, list) else ():
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()[:120]
        note = str(item.get("note") or "").strip()[:400]
        if term and note:
            items.append({"term": term, "note": note})
    return items[:4]


def _structure(raw: Any, source: str) -> list[dict[str, str]]:
    """Sentence parts, in order, each a literal piece of the selection.

    A chunk the model paraphrased, or one out of order, is dropped rather than
    shown: a structure that does not match the sentence the learner is looking at
    teaches the wrong thing.
    """
    items: list[dict[str, str]] = []
    cursor = 0
    for item in raw if isinstance(raw, list) else ():
        if not isinstance(item, dict):
            continue
        chunk = str(item.get("chunk") or "").strip()
        role = str(item.get("role") or "").strip().casefold()
        at = source.find(chunk, cursor) if chunk else -1
        if at < 0 or role not in STRUCTURE_ROLES:
            continue
        items.append({"chunk": chunk, "role": role})
        cursor = at + len(chunk)
    return items[:12]


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
            "context_meaning": {"type": "string"},
            "core_idea": {"type": "string"},
            "mental_model": {"type": "string"},
            "common_mistake": {"type": "string"},
            "contrast": {
                "type": "array",
                "maxItems": 4,
                "items": {
                    "type": "object",
                    "properties": {"term": {"type": "string"}, "note": {"type": "string"}},
                    "required": ["term", "note"],
                },
            },
            "structure": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk": {"type": "string"},
                        "role": {"type": "string", "enum": list(STRUCTURE_ROLES)},
                    },
                    "required": ["chunk", "role"],
                },
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
            "context_meaning",
            "core_idea",
            "mental_model",
            "common_mistake",
            "contrast",
            "structure",
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
        "Also give: context_meaning, a short gloss - one clause, no more - of what the "
        "selection means in this sentence, as a dictionary would give it for this use; "
        "core_idea, one plain sentence on what the selection means in "
        "general; mental_model, a short image or analogy that makes the meaning "
        "stick; common_mistake, the misunderstanding learners most often have, "
        "or an empty string if there is no real one; contrast, near-equivalents a "
        "learner might confuse it with, each with the one-line difference, or an "
        "empty list if there is none; structure, only when the selection is a whole "
        "sentence: its consecutive parts, each copied exactly from the selection and "
        "in order, with the role subject, verb, adverbial or complement (an object "
        "or any other part is a complement), otherwise an empty list. "
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
        "context_meaning": str(raw.get("context_meaning") or "").strip()[:300],
        "core_idea": str(raw.get("core_idea") or "").strip()[:600],
        "mental_model": str(raw.get("mental_model") or "").strip()[:800],
        "common_mistake": str(raw.get("common_mistake") or "").strip()[:800],
        "contrast": _contrast(raw.get("contrast")),
        "structure": _structure(raw.get("structure"), source),
        "question": question,
        "claim": "contextual_ai_explanation",
    }


def _spoken_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "carried": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["quote", "why"],
                },
            },
            "landed_differently": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "quote": {"type": "string"},
                        "why": {"type": "string"},
                        "instead": {"type": "string"},
                        "judgement": {"type": "string", "enum": list(USAGE_JUDGEMENTS)},
                    },
                    "required": ["quote", "why", "instead", "judgement"],
                },
            },
            "another_way": {"type": "string"},
            "next_attempt": {"type": "string"},
        },
        "required": ["carried", "landed_differently", "another_way", "next_attempt"],
    }


@contextual_router.post("/spoken-response")
def coach_spoken_response(payload: SpokenResponseIn) -> dict[str, Any]:
    """Coach what a learner said, from the words recognition returned.

    This is coaching, not measurement, and the surface must keep the two apart.
    Nothing here heard the audio: pronunciation, pace and intonation are not
    knowable from a transcript, and the prompt forbids commenting on them. What
    is knowable is the language the learner reached for, so that is what comes
    back - quoted from their own words, in the same judgement vocabulary the
    rest of the product uses to say what kind of problem something is.
    """
    language = _validated_source_language(payload.source_language)
    target = _support_language(payload.target_language)
    target_name = _SUPPORT_LANGUAGE_NAMES.get(target, target)
    source_name = "Simplified Chinese" if language == "zh" else "English"
    transcript = payload.transcript.strip()
    situation = payload.situation.strip()
    if not transcript:
        raise HTTPException(422, "A transcript is required.")

    system = (
        f"You are a speaking tutor. The learner speaks {source_name}; explain in "
        f"{target_name}. You are reading a speech-recognition transcript of what "
        "they said. You did NOT hear the audio: never comment on pronunciation, "
        "accent, pace, volume or intonation, and never say how they sounded. "
        "Recognition can mishear; if a fragment looks like a recognition error "
        "rather than a learner choice, leave it alone. Spoken language is not "
        "written language: false starts, contractions, fillers and short "
        "sentences are normal speech, not mistakes. Quote only words that appear "
        "in the transcript. Name at most three things that carried the meaning "
        "and at most three that would land differently, each with the reason. "
        "Give one alternative way to say part of it, not a rewrite of the whole "
        "response, and one concrete thing to try in the next attempt. Do not "
        "score, grade or estimate a level. Never cite a source you were not given."
    )
    user = (
        (f"THE SITUATION:\n{situation}\n\n" if situation else "")
        + f"WHAT RECOGNITION HEARD:\n{transcript}\n\n"
        + "Coach this spoken response."
    )
    raw = _run_structured(
        "learner_dictionary",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        schema=_spoken_schema(),
        max_output_tokens=1400,
    )

    def _grounded(items: Any, *, with_alternative: bool) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for item in items if isinstance(items, list) else ():
            if not isinstance(item, dict):
                continue
            quote = str(item.get("quote") or "").strip()
            why = str(item.get("why") or "").strip()
            # A quotation the learner did not say is the one thing coaching
            # must never show: they cannot tell a tutor's slip from their own.
            if not quote or not why or quote not in transcript:
                continue
            entry = {"quote": quote[:400], "why": why[:900]}
            if with_alternative:
                entry["instead"] = str(item.get("instead") or "").strip()[:400]
                entry["judgement"] = _judgement(item.get("judgement"))
            found.append(entry)
        return found[:3]

    carried = _grounded(raw.get("carried"), with_alternative=False)
    landed = _grounded(raw.get("landed_differently"), with_alternative=True)
    return {
        "source_language": language,
        "target_language": target,
        "transcript": transcript,
        "situation": situation,
        "carried": carried,
        "landed_differently": landed,
        "another_way": str(raw.get("another_way") or "").strip()[:600],
        "next_attempt": str(raw.get("next_attempt") or "").strip()[:400],
        "available": bool(carried or landed),
        # Said in the payload as well as in the copy: this is derived from a
        # transcript, and it is not a measurement of speech.
        "claim": "spoken_response_coaching_from_transcript",
    }


# The registers Orena contrasts. Naming them keeps the answer comparable across
# requests, and keeps "formal" from meaning something different every time.
REGISTERS = (
    "conversational",
    "concise_professional",
    "formal",
    "academic",
    "technical",
)


def _register_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "meaning": {"type": "string"},
            "versions": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "register": {"type": "string", "enum": list(REGISTERS)},
                        "text": {"type": "string"},
                        "why": {"type": "string"},
                        "signals": {
                            "type": "array",
                            "maxItems": 4,
                            "items": {"type": "string"},
                        },
                        "use_when": {"type": "string"},
                        "avoid_when": {"type": "string"},
                    },
                    "required": [
                        "register",
                        "text",
                        "why",
                        "signals",
                        "use_when",
                        "avoid_when",
                    ],
                },
            },
            "what_changes": {"type": "string"},
        },
        "required": ["meaning", "versions", "what_changes"],
    }


# Mounted beside the contextual explanation because it is the same family of
# question - what does this language do, and why - asked about a whole piece
# rather than a selection. `router` itself is not included by the app.
@contextual_router.post("/registers")
def explore_registers(payload: RegisterExploreIn) -> dict[str, Any]:
    """Show one meaning across registers, and teach what moves between them.

    This is deliberately not a rewrite endpoint. Every version must be
    accompanied by the signals that put it in that register and by when it
    would be the wrong choice, because the learning is in the difference rather
    than in any single sentence.
    """
    language = _validated_source_language(payload.source_language)
    target = _support_language(payload.target_language)
    target_name = _SUPPORT_LANGUAGE_NAMES.get(target, target)
    source_name = "Simplified Chinese" if language == "zh" else "English"
    source = payload.text.strip()
    situation = payload.situation.strip()
    if not source:
        raise HTTPException(422, "Text is required.")

    system = (
        f"You are a writing tutor. The learner writes {source_name}; explain in "
        f"{target_name}. Express the SAME meaning in each register: "
        "conversational, concise_professional, formal, academic, technical. "
        "Keep the learner's meaning; do not add claims, details or opinions "
        "they did not write. For each version give the concrete signals that "
        "place it in that register - word choice, sentence length, hedging, "
        "agency, terminology - and say when it would be the wrong choice. "
        "Teach what moves between the versions in what_changes. Do not present "
        "one version as correct and the others as mistakes; each is right "
        "somewhere. Never cite a style guide, standard or corpus you were not "
        "given."
    )
    user = (
        f"LEARNER TEXT:\n{source}\n\n"
        + (f"WRITING FOR:\n{situation}\n\n" if situation else "")
        + "Show this meaning in each register and teach the differences."
    )
    raw = _run_structured(
        "learner_dictionary",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        schema=_register_schema(),
        max_output_tokens=2000,
    )
    versions = []
    for item in raw.get("versions", []) if isinstance(raw.get("versions"), list) else ():
        if not isinstance(item, dict):
            continue
        register = str(item.get("register") or "").strip().casefold()
        text = str(item.get("text") or "").strip()
        if register not in REGISTERS or not text:
            continue
        versions.append(
            {
                "register": register,
                "text": text[:1200],
                "why": str(item.get("why") or "").strip()[:900],
                "signals": [
                    str(signal).strip()[:180]
                    for signal in item.get("signals", [])
                    if str(signal).strip()
                ][:4],
                "use_when": str(item.get("use_when") or "").strip()[:400],
                "avoid_when": str(item.get("avoid_when") or "").strip()[:400],
            }
        )
    return {
        "source_language": language,
        "target_language": target,
        "text": source,
        "situation": situation,
        "meaning": str(raw.get("meaning") or "").strip()[:1200],
        "what_changes": str(raw.get("what_changes") or "").strip()[:1600],
        "versions": versions,
        "available": bool(versions),
        "claim": "register_comparison" if versions else "register_comparison_unavailable",
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
