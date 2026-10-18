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


# --- ties: what the zero-cost rules above cannot decide (D-228) -----------------------------------------------------

MAX_TIED = 6
_SENTENCE_END = "。！？!?.\n；;"
MAX_SENTENCE_CHARS = 300


def catalogue_ties(entries: Sequence[Mapping[str, Any]], tagged_pos: str, target: str) -> list[Mapping[str, Any]]:
    """The published senses `pick_catalogue_entry` could not tell apart, in catalogue order; ``[]`` when it decided.

    A tie is two or more senses, each with a meaning in the support language (a sense with none could not be shown),
    that are equally good by the same rank: the same class match, and a distinct meaning. The first of them is the
    neutral sense `pick_catalogue_entry` returns."""

    wanted = canonical_pos(tagged_pos)
    ranked = [
        (0 if wanted and canonical_pos(entry.get("part_of_speech")) == wanted else 1, entry)
        for entry in entries
        if _target_text(entry, target)
    ]
    if len(ranked) < 2:
        return []
    best = min(rank for rank, _ in ranked)
    group, seen = [], set()
    for rank, entry in ranked:
        text = _target_text(entry, target).casefold()
        if rank == best and text not in seen:
            seen.add(text)
            group.append(entry)
    if len(group) < 2 or pick_catalogue_entry(entries, tagged_pos, target) is not group[0]:
        return []  # the sense shown is not one of the tied ones (a class match without a meaning in this language)
    return group[:MAX_TIED]


def catalogue_tie_texts(group: Sequence[Mapping[str, Any]], target: str) -> list[str]:
    return [_target_text(entry, target) for entry in group]


def definition_ties(definitions: Sequence[Any], tagged_pos: str) -> list[Any]:
    """The dictionary definitions of the word's class (all of them when none has that class or the class is unknown)
    when there are two or more with different text; ``[]`` when the class leaves a single definition."""

    wanted = canonical_pos(tagged_pos)
    matching = [d for d in definitions if wanted and canonical_pos(getattr(d, "part_of_speech", "")) == wanted]
    group, seen = [], set()
    for item in matching or list(definitions):
        text = str(getattr(item, "definition", "") or "").strip().casefold()
        if text and text not in seen:
            seen.add(text)
            group.append(item)
    return group[:MAX_TIED] if len(group) >= 2 else []


def sentence_around(context: str, selection: str, at: int | None = None) -> str:
    """The sentence of `context` that holds the tapped `selection`, at most `MAX_SENTENCE_CHARS`; ``""`` when unknown.

    `at` is the offset of the tapped occurrence when the caller knows it. Without it, the word is matched on word
    boundaries (a Latin word never inside a longer word) and, when it stands in more than one different sentence, the
    tapped one cannot be told: the answer is ``""`` and the tap keeps its neutral sense. Pure and local."""

    raw = str(context or "")
    text = raw if "\n" in raw else " ".join(raw.split())
    word = str(selection or "").strip()
    if not word:
        return ""
    lowered, needle = text.casefold(), word.casefold()
    spaced = not _is_han(needle)  # Chinese has no spaces: no word boundary to respect
    starts: list[int] = []
    pos = lowered.find(needle)
    while pos >= 0:
        before = lowered[pos - 1] if pos > 0 else " "
        after = lowered[pos + len(needle)] if pos + len(needle) < len(lowered) else " "
        inside_word = (before.isalnum() and needle[0].isalnum()) or (after.isalnum() and needle[-1].isalnum())
        if not (spaced and inside_word):
            starts.append(pos)
        pos = lowered.find(needle, pos + 1)
    if at is not None:
        starts = [pos for pos in starts if pos == at]
    sentences = {_sentence_span(text, pos, len(word)) for pos in starts}
    if len(sentences) != 1:
        return ""
    start, end = next(iter(sentences))
    sentence = " ".join(text[start:end].split())
    if len(sentence) <= MAX_SENTENCE_CHARS:
        return sentence
    inside = sentence.casefold().find(needle)
    half = (MAX_SENTENCE_CHARS - len(word)) // 2
    lo = max(0, inside - half)
    return sentence[lo : lo + MAX_SENTENCE_CHARS].strip()


def _is_han(text: str) -> bool:
    return any("\u3400" <= ch <= "\u9fff" or "\uf900" <= ch <= "\ufaff" for ch in text)


def _sentence_span(text: str, at: int, length: int) -> tuple[int, int]:
    start = max((text.rfind(mark, 0, at) for mark in _SENTENCE_END), default=-1) + 1
    ends = [i for i in (text.find(mark, at + length) for mark in _SENTENCE_END) if i >= 0]
    return start, (min(ends) + 1 if ends else len(text))
