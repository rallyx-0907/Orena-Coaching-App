"""Deterministic Chinese word lookup from the vendored CC-CEDICT + Unihan pack.

A Chinese language adapter in the sense of `ARCHITECTURE_INVARIANTS.md`: Chinese
has no free dictionary API the way English has, so the dataset is vendored here
(`docs/ORENA_AI_COST_REDUCTION_PLAN.md` P1). There is no AI in this module. A word
the pack does not carry is reported as absent rather than guessed, and every
sense returned is CC-CEDICT's own text, credited as such by its callers.
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

DATA_DIR = Path(__file__).resolve().parent / "lexicon_data"
INDEX_PATH = DATA_DIR / "zh_lexicon.index.json"
PACK_PATH = DATA_DIR / "zh_lexicon.pack"
EXPECTED_FORMAT = "orena.zh-lexicon.v1"

SOURCE_ID = "cc-cedict"
SOURCE_LABEL = "CC-CEDICT"
SOURCE_LICENSE = "CC BY-SA 4.0"
MAX_SHORT_SENSES = 3

# Senses CC-CEDICT uses for bookkeeping rather than meaning: measure-word
# references, cross-references and variant pointers. They are true and useful
# in a full entry, but they are not what "what does this word mean" asks.
_NOT_A_MEANING = re.compile(
    r"^(CL:|see |see also |variant of |old variant of |erhua variant of |"
    r"Japanese variant of |abbr\. for |used in |surname |\(old\) variant)",
    re.IGNORECASE,
)
_SYLLABLE = re.compile(r"^([A-Za-z:]+)([1-5])$")
_TONES = {
    "a": "āáǎà", "e": "ēéěè", "i": "īíǐì", "o": "ōóǒò", "u": "ūúǔù", "ü": "ǖǘǚǜ",
}


class LexiconUnavailable(RuntimeError):
    """The vendored pack is missing or unreadable."""


@dataclass(frozen=True)
class LexiconEntry:
    simplified: str
    traditional: str
    pinyin: str
    senses: tuple[str, ...]
    proper_noun: bool


def _mark(syllable: str) -> str:
    """One numbered CC-CEDICT syllable (``xue2``, ``lu:4``) in tone-mark pinyin."""

    match = _SYLLABLE.match(syllable)
    if not match:
        return syllable.replace("u:", "ü")
    letters, tone = match.group(1).replace("u:", "ü").replace("v", "ü"), int(match.group(2))
    if tone == 5:
        return letters
    lower = letters.lower()
    if "a" in lower:
        position = lower.index("a")
    elif "e" in lower:
        position = lower.index("e")
    elif "ou" in lower:
        position = lower.index("o")
    else:
        position = max(lower.rfind(vowel) for vowel in "iouü")
        if position < 0:
            return letters
    vowel = lower[position]
    marked = _TONES[vowel][tone - 1]
    if letters[position].isupper():
        marked = marked.upper()
    return letters[:position] + marked + letters[position + 1:]


def tone_marked(pinyin: str) -> str:
    """CC-CEDICT's numbered pinyin, syllable by syllable, in tone marks."""

    return " ".join(_mark(part) for part in pinyin.split())


@lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    if not INDEX_PATH.is_file() or not PACK_PATH.is_file():
        raise LexiconUnavailable("The Chinese lexicon pack is not installed.")
    try:
        payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise LexiconUnavailable("The Chinese lexicon index is unreadable.") from exc
    if payload.get("format") != EXPECTED_FORMAT or not isinstance(payload.get("offsets"), dict):
        raise LexiconUnavailable(f"The Chinese lexicon index is not {EXPECTED_FORMAT!r}.")
    return payload


def installed() -> bool:
    try:
        _index()
    except LexiconUnavailable:
        return False
    return True


def provenance() -> dict[str, Any]:
    """Which releases answer, for content provenance records."""

    sources = _index().get("sources") or {}
    cedict = sources.get("cc_cedict") or {}
    return {
        "source": SOURCE_ID,
        "label": SOURCE_LABEL,
        "license": SOURCE_LICENSE,
        "release": cedict.get("release_date", ""),
        "sha256": cedict.get("sha256", ""),
    }


@lru_cache(maxsize=2048)
def _record(char: str) -> dict[str, Any]:
    location = _index()["offsets"].get(char)
    if not location:
        return {}
    offset, length = location
    try:
        with PACK_PATH.open("rb") as handle:
            handle.seek(offset)
            blob = handle.read(length)
        return json.loads(zlib.decompress(blob).decode("utf-8"))
    except (OSError, ValueError, zlib.error) as exc:
        raise LexiconUnavailable("The Chinese lexicon pack is unreadable.") from exc


def _clean(word: str) -> str:
    return "".join(unicodedata.normalize("NFC", str(word or "")).split())


def lookup(word: str) -> tuple[LexiconEntry, ...]:
    """Every CC-CEDICT entry for a simplified headword, common words first."""

    clean = _clean(word)
    if not clean:
        return ()
    rows = (_record(clean[0]).get("w") or {}).get(clean) or []
    entries = [
        LexiconEntry(
            simplified=clean,
            traditional=str(traditional),
            pinyin=tone_marked(str(pinyin)),
            senses=tuple(str(sense) for sense in senses),
            # CC-CEDICT capitalises the pinyin of names and places.
            proper_noun=str(pinyin)[:1].isupper(),
        )
        for traditional, pinyin, senses in rows
    ]
    return tuple(sorted(entries, key=lambda entry: entry.proper_noun))


# Register-marked senses ("(slang) ...", "(archaic) ...") and senses that carry
# CC-CEDICT's bracketed pinyin cross-references are used only when an entry has
# no plain sense: a short meaning names the ordinary use.
_MARKED = re.compile(r"^\((slang|Internet slang|dialect|archaic|old|literary|euphemism|vulgar)\)", re.IGNORECASE)


def meaning_senses(entry: LexiconEntry) -> tuple[str, ...]:
    senses = [sense for sense in entry.senses if not _NOT_A_MEANING.match(sense)]
    plain = [sense for sense in senses if not _MARKED.match(sense) and "[" not in sense]
    return tuple(plain or senses)


def short_meaning(word: str) -> str:
    """The first senses of the first common entry that carries any, or ``""``."""

    for entry in lookup(word):
        senses = meaning_senses(entry)
        if senses:
            return "; ".join(senses[:MAX_SHORT_SENSES])
    return ""


def reading(word: str) -> str:
    """Tone-marked pinyin of the first common entry, or ``""``."""

    entries = lookup(word)
    return entries[0].pinyin if entries else ""


def character(char: str) -> dict[str, str]:
    """Unihan's Mandarin reading, Vietnamese readings and definition for one character.

    ``vietnamese`` is Unihan's ``kVietnamese`` as published: it mixes Sino-
    Vietnamese (Hán-Việt) and Nôm readings in no stated order (森 lists "chùm"
    before "sâm"), so it must not be presented as the Hán-Việt reading.
    """

    record = _record(char) if len(char) == 1 else {}
    readings = record.get("c") or {}
    return {
        "mandarin": str(readings.get("m") or ""),
        "vietnamese": str(readings.get("v") or ""),
        "definition": str(readings.get("d") or ""),
    }
