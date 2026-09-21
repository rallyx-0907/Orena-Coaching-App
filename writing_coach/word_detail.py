"""The Quick Sheet's two contracts: WordDetail and SentenceSheet (D-066).

The canonical UI (`docs/design/canonical-ui/data-contracts/WordDetail.json` and
`SentenceSheet.json`) decides these shapes. This module is the projection from
what the backend already knows - the deterministic lookup and the contextual
explanation - into them. The projection functions are pure: no provider, no I/O,
so the contract can be tested without either.

Two different questions stay two different paths (D-066 rule 8):

- the basic lookup (headword, reading, part of speech, dictionary meaning) is
  deterministic and never reaches a provider;
- "nghĩa ở câu này" is a contextual meaning, and comes from the explanation
  capability through the provider abstraction. When that is unavailable the
  sheet still answers from the dictionary, and says which it did in
  `meaningSource` rather than presenting a dictionary sense as a contextual one.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from writing_coach import media_interaction
from writing_coach.core.errors import orena_http_error

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])

# The explanation's judgement (snake_case, the provider contract) to the
# canonical `usageVerdict` value the UI draws. One table, so the two vocabularies
# cannot drift apart.
USAGE_VERDICTS: Mapping[str, str] = {
    "natural": "natural",
    "possible_but_unnatural": "possible-unnatural",
    "contextually_inappropriate": "context-inappropriate",
    "wrong_for_intended_meaning": "wrong-meaning",
    "register_mismatch": "register-mismatch",
    "uncommon_but_legitimate": "uncommon-legit",
    "grammatically_impossible": "grammatically-impossible",
}
assert set(USAGE_VERDICTS) == set(media_interaction.USAGE_JUDGEMENTS)

_HAN = re.compile(r"[㐀-鿿豈-﫿]")

# What a caller supplies. Both are set once at start-up (app.py) so the module
# does not import the persistence layer.
_lookup: Callable[[str, str, str, str], Any] | None = None
_saved_terms: Callable[[], set[str]] | None = None


def configure_word_detail(
    *,
    lookup: Callable[[str, str, str, str], Any] | None,
    saved_terms: Callable[[], set[str]] | None,
) -> None:
    global _lookup, _saved_terms
    _lookup = lookup
    _saved_terms = saved_terms


def usage_verdict(judgement: object) -> str | None:
    """The canonical verdict for an explanation judgement, or None if unknown."""
    return USAGE_VERDICTS.get(str(judgement or "").strip())


def script_of(language: str, headword: str) -> str:
    return "hanzi" if language == "zh" or _HAN.search(headword or "") else "latin"


def _text(value: object) -> str:
    return str(value or "").strip()


def _join(items: object) -> str:
    return "\n".join(_text(item) for item in items or () if _text(item))


def project_word_detail(
    *,
    selection: str,
    context: str,
    language: str,
    lookup: Mapping[str, Any] | None,
    explanation: Mapping[str, Any] | None,
    saved: bool,
) -> dict[str, Any]:
    """WordDetail.json from a lookup result and an explanation, either optional."""
    found = lookup or {}
    said = explanation or {}
    pronunciation = _text(found.get("pronunciation"))
    headword = _text(found.get("base_form")) or _text(selection)
    script = script_of(language, headword)

    dictionary_meaning = ""
    meanings = found.get("meanings") or ()
    if meanings:
        dictionary_meaning = _text(meanings[0].get("text"))
    elif found.get("definitions"):
        dictionary_meaning = _text(found["definitions"][0].get("definition"))
    # The short gloss is the meaning in this sentence; the summary is the longer
    # explanation and only stands in when the gloss is absent.
    contextual = _text(said.get("context_meaning")) or _text(said.get("summary"))
    if contextual:
        meaning, source = contextual, "context"
    elif dictionary_meaning:
        meaning, source = dictionary_meaning, "dictionary"
    else:
        meaning, source = "", "none"

    part_of_speech = _text(found.get("part_of_speech"))
    if not part_of_speech:
        for item in said.get("vocabulary") or ():
            if _text(item.get("fragment")).casefold() == _text(selection).casefold():
                part_of_speech = _text(item.get("pos"))
                break

    related = [
        {"term": _text(item.get("fragment")), "note": _text(item.get("meaning"))}
        for item in said.get("vocabulary") or ()
        if _text(item.get("fragment")).casefold() != _text(selection).casefold()
    ]
    return {
        "headword": headword,
        "script": script,
        # A Chinese reading is pinyin; for an alphabetic language it is the
        # dictionary's phonetic. Nothing here invents the one that is absent.
        "pinyin": pronunciation if script == "hanzi" and pronunciation else None,
        "ipa": pronunciation if script == "latin" and pronunciation else None,
        "partOfSpeech": part_of_speech or None,
        "contextMeaning": meaning,
        "contextSentence": _text(context),
        "audioUrl": _text(found.get("audio_url")),
        "saved": bool(saved),
        "deeper": {
            "coreIdea": _text(said.get("core_idea")),
            "mentalModel": _text(said.get("mental_model")),
            "whyHere": _text(said.get("judgement_reason")) or _text(said.get("usage_note")),
            "contrast": [
                {"term": _text(item.get("term")), "note": _text(item.get("note"))}
                for item in said.get("contrast") or ()
                if _text(item.get("term"))
            ],
            "examples": [_text(item.get("text")) for item in said.get("examples") or () if _text(item.get("text"))],
            "commonMistake": _text(said.get("common_mistake")),
            "grammarNote": _join(said.get("grammar_notes")),
            "relatedExpressions": related,
            # Where the learner met it, and their own sentences, come from
            # learner-owned memory the server does not hold yet (UI_BACKEND_GAPS
            # QS-7); an honest empty list until it does.
            "sources": [],
            "learnerSentences": [],
        },
        "usageVerdict": usage_verdict(said.get("judgement")) if said else None,
        "meaningSource": source,
    }


def project_sentence_sheet(
    *,
    sentence: str,
    explanation: Mapping[str, Any],
    saved_terms: set[str],
) -> dict[str, Any]:
    """SentenceSheet.json from a sentence's explanation."""
    return {
        "sentence": _text(sentence),
        "translation": _text(explanation.get("natural_translation")),
        "shortExplanation": _text(explanation.get("summary")),
        "structure": [
            {"chunk": _text(item.get("chunk")), "role": _text(item.get("role"))}
            for item in explanation.get("structure") or ()
            if _text(item.get("chunk"))
        ],
        "vocabulary": [
            {
                "term": _text(item.get("fragment")),
                "meaning": _text(item.get("meaning")),
                "saved": _text(item.get("fragment")).casefold() in saved_terms,
            }
            for item in explanation.get("vocabulary") or ()
            if _text(item.get("fragment"))
        ],
    }


class WordDetailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # "sheet" is the first layer: a short gloss, answered at once. "full" is the
    # explanation behind "why here?", asked for only when the learner opens it.
    depth: Literal["sheet", "full"] = "full"

    text: str = Field(min_length=1, max_length=80)
    context: str = Field(min_length=1, max_length=1200)
    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    question: str = Field(default="", max_length=400)

    @field_validator("target_language")
    @classmethod
    def _normalize_target(cls, value: str) -> str:
        return value.strip().casefold()


class SentenceSheetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=1600)
    context: str = Field(default="", max_length=2400)
    source_language: str = Field(min_length=2, max_length=32)
    target_language: str = Field(min_length=2, max_length=32)
    question: str = Field(default="", max_length=400)

    @field_validator("target_language")
    @classmethod
    def _normalize_target(cls, value: str) -> str:
        return value.strip().casefold()


def _gloss(text: str, context: str, source: str, target: str) -> dict[str, Any] | None:
    """A short contextual gloss, or None when the capability is unavailable."""
    try:
        result = media_interaction.meaning_in_context(
            media_interaction.MediaExplainIn(
                text=text, context=context, source_language=source, target_language=target
            )
        )
    except HTTPException as exc:
        if exc.status_code in {502, 503}:
            return None
        raise
    return result if _text(result.get("context_meaning")) else None


def _explain(text: str, context: str, source: str, target: str, question: str) -> dict[str, Any] | None:
    """The contextual explanation, or None when the capability is unavailable."""
    try:
        result = media_interaction.explain_media_text(
            media_interaction.MediaExplainIn(
                text=text,
                context=context,
                source_language=source,
                target_language=target,
                question=question,
            )
        )
    except HTTPException as exc:
        if exc.status_code in {502, 503}:
            return None
        raise
    return result if _text(result.get("summary")) else None


def _saved() -> set[str]:
    try:
        return {term.casefold() for term in (_saved_terms() if _saved_terms else set())}
    except Exception:
        return set()


@router.post("/word-detail")
def word_detail(payload: WordDetailIn) -> dict[str, Any]:
    text = payload.text.strip()
    context = payload.context.strip()
    if not text or text.casefold() not in context.casefold():
        raise orena_http_error(
            422,
            "word_detail_text_not_in_context",
            "Selected text must come from the supplied learner context.",
            retryable=False,
        )
    source = media_interaction._primary_language(payload.source_language)
    lookup: dict[str, Any] = {}
    if _lookup is not None:
        try:
            lookup = _lookup(text, context, source, payload.target_language).to_dict()
        except Exception:  # noqa: BLE001 - a failed dictionary must not fail the sheet
            lookup = {}
    if payload.depth == "sheet" and not payload.question.strip():
        explanation = _gloss(text, context, source, payload.target_language)
    else:
        explanation = _explain(text, context, source, payload.target_language, payload.question)
    detail = project_word_detail(
        selection=text,
        context=context,
        language=source,
        lookup=lookup,
        explanation=explanation,
        saved=text.casefold() in _saved(),
    )
    available = detail["meaningSource"] != "none"
    return {
        **detail,
        # A follow-up is this same call carrying the learner's question; the
        # explanation's summary is then the answer to it, not the word's meaning.
        "depth": payload.depth,
        "answer": _text(explanation.get("summary")) if payload.question.strip() and explanation else "",
        # The questions the baseline offers first, phrased for this word.
        "followUps": [_text(item) for item in (explanation or {}).get("follow_ups") or () if _text(item)],
        "available": available,
        "claim": "word_detail" if available else "word_detail_unavailable",
    }


@router.post("/sentence-sheet")
def sentence_sheet(payload: SentenceSheetIn) -> dict[str, Any]:
    sentence = payload.text.strip()
    explanation = _explain(
        sentence,
        payload.context.strip() or sentence,
        media_interaction._primary_language(payload.source_language),
        payload.target_language,
        payload.question,
    )
    if explanation is None:
        return {
            "available": False,
            "claim": "sentence_sheet_unavailable",
            "sentence": sentence,
        }
    return {
        **project_sentence_sheet(sentence=sentence, explanation=explanation, saved_terms=_saved()),
        "answer": _text(explanation.get("summary")) if payload.question.strip() else "",
        "available": True,
        "claim": "sentence_sheet",
    }
