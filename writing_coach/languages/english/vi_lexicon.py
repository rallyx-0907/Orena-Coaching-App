"""Deterministic English -> Vietnamese word lookup from the vendored English Wiktionary pack (D-246).

The EN->VI counterpart of the vendored CC-CEDICT (`writing_coach.languages.chinese.lexicon`): a word's base meaning
in Vietnamese is a dataset fact, so it is looked up here, never asked of a language model. The data is the English
Wiktionary's Vietnamese translation tables, extracted by Wiktextract (kaikki.org), CC BY-SA 4.0; the pack lives in
`vi_lexicon_data/` with its licence text, provenance and modification notice, and is built by
`scripts/build_en_vi_pack.py`. A word the pack does not carry is reported as absent, never guessed: it falls through
to the next layer of the word tap (local translation, then the `word_translation` seam and its cache).

Each sense keeps its English sense label, so the sense that fits is chosen deterministically: by the word's part of
speech in the sentence, then by the sense label's words in the sentence, otherwise the common sense (the pack orders
each entry's senses common first).
"""

from __future__ import annotations

import json
import re
import unicodedata
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "vi_lexicon_data"
INDEX_PATH = DATA_DIR / "en_vi_lexicon.index.json"
PACK_PATH = DATA_DIR / "en_vi_lexicon.pack"
EXPECTED_FORMAT = "orena.en-vi-lexicon.v1"
PREFIX_LENGTH = 2

SOURCE_ID = "wiktionary-en-vi"
SOURCE_LABEL = "Wiktionary"
SOURCE_LICENSE = "CC BY-SA 4.0"
MAX_GLOSSES = 2

# The product's part-of-speech labels (`linguistic_annotation.ALLOWED_POS`) -> the Wiktextract parts of speech that
# answer them. A label not here (particle, classifier, other, empty) does not narrow the choice.
_POS_MATCH: dict[str, frozenset[str]] = {
    "noun": frozenset({"noun"}),
    "proper_noun": frozenset({"name", "noun"}),
    "verb": frozenset({"verb"}),
    "auxiliary": frozenset({"verb"}),
    "adjective": frozenset({"adj"}),
    "adverb": frozenset({"adv"}),
    "pronoun": frozenset({"pron"}),
    "determiner": frozenset({"det", "article"}),
    "preposition": frozenset({"prep"}),
    "conjunction": frozenset({"conj"}),
    "numeral": frozenset({"num"}),
    "interjection": frozenset({"intj"}),
}
_WORD = re.compile(r"[a-z]+")
# Words a sense label shares with any sentence: never evidence of the sense.
_STOP = frozenset(
    "the and for with that this from into onto upon over under than then them they their there these those which "
    "who whom whose what when where while some any something someone one ones its it's not are was were been being "
    "have has had having can could may might must shall should will would very more most such other another each "
    "also only just about used using use make made makes making cause causes something especially particularly "
    "transitive intransitive informal formal figurative literally".split()
)


class LexiconUnavailable(RuntimeError):
    """The vendored pack is missing or unreadable."""


@dataclass(frozen=True)
class ViSense:
    part_of_speech: str  # Wiktextract's: noun, verb, adj, adv, name, ...
    sense: str  # the English sense label of the translation table ("armor", "device storing electricity")
    glosses: tuple[str, ...]  # Vietnamese, NFC, most current first

    @property
    def gloss(self) -> str:
        return "; ".join(self.glosses[:MAX_GLOSSES])


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    if not INDEX_PATH.is_file() or not PACK_PATH.is_file():
        raise LexiconUnavailable("The English-Vietnamese pack is not installed.")
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LexiconUnavailable("The English-Vietnamese pack index is unreadable.") from exc
    if payload.get("format") != EXPECTED_FORMAT or not isinstance(payload.get("offsets"), dict):
        raise LexiconUnavailable(f"The English-Vietnamese pack index is not {EXPECTED_FORMAT!r}.")
    return payload


def installed() -> bool:
    try:
        _index()
    except LexiconUnavailable:
        return False
    return True


def provenance() -> dict[str, Any]:
    """Which release answers, for content provenance records."""

    source = (_index().get("sources") or {}).get("wiktionary_en") or {}
    return {
        "source": SOURCE_ID,
        "label": SOURCE_LABEL,
        "license": SOURCE_LICENSE,
        "release": source.get("release", ""),
        "sha256": source.get("sha256", ""),
    }


@lru_cache(maxsize=512)
def _record(prefix: str) -> dict[str, Any]:
    location = _index()["offsets"].get(prefix)
    if not location:
        return {}
    offset, length = location
    try:
        with PACK_PATH.open("rb") as handle:
            handle.seek(offset)
            blob = handle.read(length)
        return json.loads(zlib.decompress(blob).decode("utf-8"))
    except (OSError, ValueError, zlib.error) as exc:
        raise LexiconUnavailable("The English-Vietnamese pack is unreadable.") from exc


def _clean(word: str) -> str:
    return " ".join(unicodedata.normalize("NFC", str(word or "")).split())


# Regular English inflections, tried only when the form itself is not a headword: (suffix, endings that replace it).
# A reduction is accepted only when it names a headword of the pack (a closed set), so "adopted" reaches "adopt" and
# "amused" reaches "amuse", while a form whose reduction names nothing stays a miss. Irregular forms are not guessed.
_INFLECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ying", ("ie",)), ("ies", ("y",)), ("ied", ("y",)), ("es", ("e", "")), ("s", ("",)),
    ("ed", ("e", "")), ("ing", ("e", "")),
)
_MIN_STEM = 3
# A Wiktionary translation cell sometimes lists spelling alternatives with an English "or" ("anh or anh trai"); the
# word is not Vietnamese, so each alternative is its own gloss (the build splits them too: scripts/build_en_vi_pack.py).
_ENGLISH_OR = re.compile(r"\s+or\s+")


def _glosses(values: Any) -> tuple[str, ...]:
    out: list[str] = []
    for value in values or ():
        out.extend(part.strip() for part in _ENGLISH_OR.split(str(value)) if part.strip())
    return tuple(dict.fromkeys(out))


_VERBAL = ("ed", "ing", "ied", "ying")  # past / -ing: reduced only for a word tagged verb or adjective here
_VERBAL_POS = frozenset({"verb", "auxiliary", "adjective"})
_PLURAL_POS = frozenset({"noun", "verb", "auxiliary"})  # -s / -es / -ies: a plural noun or a third-person verb


def _base_forms(word: str, part_of_speech: str = "") -> list[str]:
    """Regular base forms of an inflected English word, most likely first (never the word itself), for the part of
    speech the word has in its sentence. Unknown part of speech: none (an "-ed" word with no class is not guessed at)."""

    lower = word.casefold()
    pos = str(part_of_speech or "").strip().casefold()
    if not lower.isalpha() or not pos:
        return []
    forms: list[str] = []
    for suffix, endings in _INFLECTIONS:
        if not lower.endswith(suffix):
            continue
        if suffix in _VERBAL and pos not in _VERBAL_POS:
            continue
        if suffix not in _VERBAL and pos not in _PLURAL_POS:
            continue
        stem = lower[: -len(suffix)]
        for ending in endings:
            if len(stem + ending) >= _MIN_STEM:
                forms.append(stem + ending)
        if suffix in {"ed", "ing"} and len(stem) >= _MIN_STEM + 1 and stem[-1] == stem[-2] and stem[-1] not in "aeiouls":
            forms.append(stem[:-1])  # stopped -> stop, running -> run
    return [form for form in dict.fromkeys(forms) if form != lower]


def _rows(key: str) -> list[Any]:
    return _record(key.casefold()[:PREFIX_LENGTH]).get(key) or []


def _senses(rows: list[Any]) -> tuple[ViSense, ...]:
    return tuple(ViSense(str(pos), str(sense), _glosses(glosses)) for pos, sense, glosses in rows if _glosses(glosses))


def lookup(word: str) -> tuple[ViSense, ...]:
    """Every Vietnamese sense of an English headword, common sense first; () when the pack has none.

    The headword as written is tried first ("US", "May"), then its lower case; a leading infinitive "to " is dropped.
    An inflected form the pack does not carry is not reduced here: `choose` does that, knowing the word's class."""

    clean = _clean(word)
    if clean.casefold().startswith("to ") and len(clean) > 3:
        clean = clean[3:].strip()
    if not clean:
        return ()
    for key in dict.fromkeys((clean, clean.casefold())):
        rows = _rows(key)
        if rows:
            return _senses(rows)
    return ()


def _syllables(gloss_text: str) -> set[str]:
    return {part for part in re.split(r"[\s;,]+", gloss_text.casefold()) if part}


def _reduced(word: str, part_of_speech: str, wanted: frozenset[str], context: str) -> ViSense | None:
    """The sense of a regular inflection's base form ("adopted" -> "adopt"), or None.

    The shared tagger's lemma only strips a plural, so a past or -ing form would always miss the pack. A base form is
    used only for the class the word has here (`wanted`), and only when its senses of that class agree: "needed" ->
    "cần" (cần / cần phải / cần; muốn), but "lied" is never "nằm" - the verb "lie" has two senses that share no word
    (lie down, tell a lie), so unless the sentence names one, the tap falls through to the next layer."""

    for base in _base_forms(word, part_of_speech):
        senses = tuple(sense for sense in lookup(base) if sense.part_of_speech in wanted)
        if not senses:
            continue
        if len(senses) == 1:
            return senses[0]
        if context:
            around = _stems(context, word) - _stems(base, "")
            scores = [len(_stems(sense.sense, base) & around) for sense in senses]
            best = max(scores)
            if best > 0 and scores.count(best) == 1:
                return senses[scores.index(best)]
        first = _syllables(senses[0].gloss)
        if all(first & _syllables(sense.gloss) for sense in senses[1:]):
            return senses[0]
        return None
    return None


def _stems(text: str, skip: str) -> set[str]:
    skip_stem = skip.casefold()[:5]
    return {
        token[:5]
        for token in _WORD.findall(text.casefold())
        if len(token) >= 3 and token not in _STOP and (not skip_stem or token[:5] != skip_stem)
    }


def choose(word: str, part_of_speech: str = "", context: str = "") -> ViSense | None:
    """The sense that fits: the word's part of speech in the sentence, then the sense label's words in the sentence,
    otherwise the common sense. None when the pack has no sense, or none of the part of speech the word has here (a
    noun's gloss is not the meaning of the adjective "light"). A form the pack lacks is reduced to its base form only
    for a known part of speech, and only to a sense of that part of speech (`_reduced`)."""

    senses = lookup(word)
    wanted = _POS_MATCH.get(str(part_of_speech or "").strip().casefold())
    if not senses:
        return _reduced(word, part_of_speech, wanted, context) if wanted and " " not in _clean(word) else None
    if wanted:
        senses = tuple(sense for sense in senses if sense.part_of_speech in wanted)
        if not senses:
            return None
    if len(senses) > 1 and context:
        around = _stems(context, word)
        if around:
            scores = [len(_stems(sense.sense, word) & around) for sense in senses]
            best = max(scores)
            if best > 0:
                return senses[scores.index(best)]
    return senses[0]


def gloss(word: str, part_of_speech: str = "", context: str = "") -> str | None:
    """The short Vietnamese meaning of the sense that fits ("khiên; lá chắn"), or None."""

    chosen = choose(word, part_of_speech, context)
    return chosen.gloss if chosen is not None and chosen.gloss else None
