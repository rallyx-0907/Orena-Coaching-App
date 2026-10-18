"""Zero-cost sense choice for a word tap (owner decision 2026-10-18, refs #194).

A tap shows the neutral basic meaning. When a word has more than one sense on file, the sentence it stands in can
usually decide between them without asking anyone: the part of speech the local tagger gave it there, and for Chinese
the reading the tagger gave it there. Every function here is pure and local: no AI, no network, no provider, no cache.
What these functions cannot decide, they leave to the existing order (first sense), which is the neutral meaning.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

# Dictionary and catalogue spellings of a class, folded onto the tagger's labels (`linguistic_annotation.ALLOWED_POS`).
_POS_ALIASES = {
    "n": "noun", "noun": "noun", "propn": "proper_noun", "proper noun": "proper_noun", "proper_noun": "proper_noun",
    "v": "verb", "verb": "verb", "vb": "verb",
    "adj": "adjective", "a": "adjective", "adjective": "adjective",
    "adv": "adverb", "adverb": "adverb",
    "pron": "pronoun", "pronoun": "pronoun",
    "prep": "preposition", "preposition": "preposition",
    "conj": "conjunction", "conjunction": "conjunction",
    "det": "determiner", "determiner": "determiner", "article": "determiner",
    "num": "numeral", "numeral": "numeral",
    "interj": "interjection", "interjection": "interjection", "exclamation": "interjection",
}


def canonical_pos(value: object) -> str:
    """The tagger's label for a class spelled as a dictionary or a catalogue spells it, or ``""``."""

    text = str(value or "").strip().casefold().rstrip(".")
    return _POS_ALIASES.get(text, "")


def definitions_by_pos(definitions: Sequence[Any], tagged_pos: str) -> list[Any]:
    """`definitions` with the ones whose class is the word's class in its sentence first, order otherwise kept.

    Items need a ``part_of_speech`` attribute. Nothing is dropped and nothing is reordered when the tagger gave no
    usable class or no definition has that class, so the dictionary's own first sense stays the neutral one."""

    wanted = canonical_pos(tagged_pos)
    if not wanted:
        return list(definitions)
    matching = [item for item in definitions if canonical_pos(getattr(item, "part_of_speech", "")) == wanted]
    if not matching:
        return list(definitions)
    return matching + [item for item in definitions if item not in matching]


def _target_text(entry: Mapping[str, Any], target: str) -> str:
    for item in entry.get("short_meanings") or ():
        if not isinstance(item, Mapping):
            continue
        if str(item.get("language") or "").strip().casefold() != target:
            continue
        text = str(item.get("text") or "").strip()
        if text:
            return text
    return ""


def pick_catalogue_entry(entries: Sequence[Mapping[str, Any]], tagged_pos: str, target: str) -> Mapping[str, Any] | None:
    """The authored sense to show among a word's published senses.

    A sense with a meaning in the support language beats one without (the pack's own localization is shown instead
    of a machine's or an English gloss) - but only among senses of the same class: the sense whose class is the word's
    class in the sentence wins first, even with no meaning in the support language (the layers below localise it).
    Ties keep the catalogue's order, which is the neutral first sense."""

    if not entries:
        return None
    wanted = canonical_pos(tagged_pos)

    def rank(indexed: tuple[int, Mapping[str, Any]]) -> tuple[int, int, int]:
        index, entry = indexed
        has_target = 0 if _target_text(entry, target) else 1
        pos_match = 0 if wanted and canonical_pos(entry.get("part_of_speech")) == wanted else 1
        return (pos_match, has_target, index)

    return min(enumerate(entries), key=rank)[1]


def _plain(pinyin: str) -> str:
    """A pinyin reading folded for comparison: tone marks, case, spaces and the umlaut do not matter."""

    decomposed = unicodedata.normalize("NFD", str(pinyin or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch) and ch.isalpha())


def _toned(pinyin: str) -> str:
    return "".join(unicodedata.normalize("NFC", str(pinyin or "").casefold()).split())


def pick_chinese_entry(entries: Sequence[Any], tagger_reading: str) -> Any | None:
    """The CC-CEDICT entry whose reading is the reading the tagger gave the word in its sentence.

    A headword with several readings (行 xíng / háng, 重 zhòng / chóng, 得 de / dé / děi) has one entry each, common
    first. The tagger reads the sentence, so its reading chooses the entry; an exact tone-marked match beats a
    toneless one. With no reading, or none that matches, the first entry stands (the neutral meaning)."""

    if not entries:
        return None
    reading = _toned(tagger_reading)
    if not reading:
        return entries[0]
    for entry in entries:
        if _toned(getattr(entry, "pinyin", "")) == reading:
            return entry
    plain = _plain(tagger_reading)
    for entry in entries:
        if _plain(getattr(entry, "pinyin", "")) == plain:
            return entry
    return entries[0]
