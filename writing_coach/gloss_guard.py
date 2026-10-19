"""When a headword gloss must not be shown for a tapped word (PRE-202 review, 2026-10-19).

A word tap attaches the pack / dictionary gloss of the headword. That is right only when the headword's sense is the
one the sentence uses. Some taps can never be confirmed that way, and for those the tap keeps its non-committal state
(no meaning; the learner can ask Orena) rather than show a wrong sense:

- ``function_word`` - an article, preposition, conjunction, auxiliary, pronoun or particle. Its job is grammatical; a
  headword gloss ("with" as an adverb, "and" as a music noun) misleads. Decided by the language's own list
  (``languages/<language>/gloss_guard.json``) and by the class the shared tagger gave the word in its sentence.
- ``proper_noun`` - the word is part of a name ("Boston Morning Post"), not the common word.
- ``multiword`` - the word is one part of an expression whose sense is not the headword's: a phrasal verb ("turn off"),
  a fixed phrase ("in turn") or a period ("late autumn", "late 1800s").

Pure, local and language-neutral: no AI, no network. The data lives in the language adapters; this module only reads it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

_LANGUAGE_DIRS = {"en": "english", "zh": "chinese"}
_LANGUAGES = Path(__file__).resolve().parent / "languages"

# The tagger labels (`linguistic_annotation.ALLOWED_POS`) of words that carry grammar, not a lexical sense.
FUNCTION_POS = frozenset(
    {"pronoun", "determiner", "preposition", "conjunction", "particle", "auxiliary", "classifier"}
)
# The labels of words that have a lexical sense of their own: only among these is a class disagreement a sense error.
CONTENT_POS = frozenset({"noun", "verb", "adjective", "adverb"})
_DIGITS = re.compile(r"^\d")


@lru_cache(maxsize=8)
def _data(language: str) -> Mapping[str, frozenset[str]]:
    """The language's lists. `name_guard` is a flag, held as a one-item set when on: only a language whose names the
    tagger can recognise reliably (English: capitalised, tagged NNP) turns it on; jieba's name flags are not reliable
    (松树 "pine" is tagged a name), so Chinese leaves it off."""

    folder = _LANGUAGE_DIRS.get(str(language or "").split("-", 1)[0].casefold())
    keys = ("name_guard", "function_words", "phrasal_particles", "fixed_expressions", "period_modifiers", "period_words")
    if folder is None:
        return {key: frozenset() for key in keys}
    path = _LANGUAGES / folder / "gloss_guard.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {key: frozenset() for key in keys}
    data = {key: frozenset(str(item).casefold() for item in raw.get(key) or ()) for key in keys[1:]}
    return {"name_guard": frozenset({"on"}) if raw.get("name_guard") else frozenset(), **data}


def is_function_word(language: str, word: str) -> bool:
    """Whether `word` is on the language's function-word list (a tagger-free check, usable before any tagging)."""

    return str(word or "").strip().casefold() in _data(language)["function_words"]


def pos_disagrees(entry_pos: str, tagged_pos: str) -> bool:
    """Whether a catalogue sense's class and the class the word has in its sentence are two different lexical classes.

    Only true when both are lexical classes (noun, verb, adjective, adverb); an unknown or grammatical label never
    counts as a disagreement."""

    from writing_coach.tap_sense import canonical_pos

    left, right = canonical_pos(entry_pos), canonical_pos(tagged_pos)
    return left in CONTENT_POS and right in CONTENT_POS and left != right


def withhold_reason(
    language: str,
    selection: str,
    tagged_pos: str,
    previous: Mapping[str, Any] | None = None,
    following: Mapping[str, Any] | None = None,
) -> str:
    """Why no headword gloss may be shown for `selection` where it stands, or ``""`` when none applies.

    `previous` / `following` are the tagger's annotations (``fragment``, ``pos``) of the neighbouring tokens, ``None``
    at a sentence edge or when the tagger is unavailable. Only a single-word selection is judged."""

    word = str(selection or "").strip().casefold()
    if not word or len(word.split()) != 1:
        return ""
    data = _data(language)
    if word in data["function_words"] or str(tagged_pos or "") in FUNCTION_POS:
        return "function_word"
    if "on" not in data["name_guard"]:
        pass
    elif str(tagged_pos or "") == "proper_noun":
        return "proper_noun"
    elif str(selection).strip()[:1].isupper() and any(str((token or {}).get("pos")) == "proper_noun" for token in (previous, following)):
        return "proper_noun"  # "Morning" between "Boston" and "Post": the tagger may call it a common noun
    before = _fragment(previous)
    after = _fragment(following)
    for phrase in (f"{before} {word}", f"{word} {after}", f"{before} {word} {after}"):
        if phrase.strip() in data["fixed_expressions"] and len(phrase.split()) > 1:
            return "multiword"
    if tagged_pos == "verb" and after in data["phrasal_particles"]:
        return "multiword"
    if word in data["period_modifiers"] and after:
        if after in data["period_words"] or _DIGITS.match(after) or str((following or {}).get("pos")) == "numeral":
            return "multiword"
    return ""


def _fragment(token: Mapping[str, Any] | None) -> str:
    # The English tokenizer leaves a sentence-final full stop on the last word ("autumn.", "1800s.").
    return str((token or {}).get("fragment") or "").strip().strip(".,;:!?\"')(").casefold()


def neighbours(
    tokens: Sequence[Mapping[str, Any]], start: int, end: int
) -> tuple[Mapping[str, Any] | None, Mapping[str, Any] | None]:
    """The tagger tokens just before and just after the span [start, end) of the selection, or ``None`` at an edge."""

    before = [token for token in tokens if int(token["end"]) <= start]
    after = [token for token in tokens if int(token["start"]) >= end]
    return (before[-1] if before else None, after[0] if after else None)
