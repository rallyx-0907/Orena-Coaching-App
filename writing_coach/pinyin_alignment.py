"""One reading under each Chinese character (D-066, DC-3).

A catalogue line carries its reviewed pinyin as words ("Wǒmen xiǎng yào yì zhāng"):
the reading an editor approved, with tone sandhi and neutral tones as spoken. The
Dictation screen draws a reading under every character, so the reviewed string has to
be cut into one syllable per character.

The cut is verifiable, not a second opinion: pypinyin is used only to learn how many
letters each character's syllable can have (all of a character's readings are
accepted, so a colloquial "shéi" for 谁 is not a mismatch), and the syllable itself
always comes from the reviewed string. If the two disagree anywhere - a different
number of syllables, a letter that does not match - the whole line is left unaligned
and the caller draws no reading for it, rather than a wrong one.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from typing import Any

from pypinyin import Style, pinyin


def _is_han(character: str) -> bool:
    code = ord(character)
    return 0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF


def _letters(reading: str) -> list[str]:
    """The letters of a reading in order, tone marks kept, spacing and punctuation dropped."""

    return [ch for ch in unicodedata.normalize("NFC", reading) if ch.isalpha()]


def _base(letter: str) -> str:
    """A letter without its tone mark or diaeresis (ǒ -> o, ü -> u), lower case."""

    return "".join(ch for ch in unicodedata.normalize("NFD", letter) if not unicodedata.combining(ch)).lower()


def _candidates(character: str) -> list[list[str]]:
    """Every reading pypinyin knows for a character, as base letters, longest first."""

    readings = pinyin(character, style=Style.NORMAL, heteronym=True, errors="ignore")
    if not readings or not readings[0]:
        return []
    found = {
        tuple(_base(letter) for letter in unicodedata.normalize("NFC", reading) if letter.isalpha())
        for reading in readings[0]
    }
    return sorted((list(item) for item in found if item), key=len, reverse=True)


def align_pinyin(text: str, reviewed: str) -> list[dict[str, str]] | None:
    """`[{"char": "我", "pinyin": "wǒ"}, ...]` for the Han characters of `text`, or None.

    Only Han characters get an entry. A Latin letter or digit in the text is a word the
    reviewed reading spells out as it is, so it must match letter for letter and is
    skipped; punctuation has no reading and is ignored.
    """

    chars = list(str(text or ""))
    if not any(_is_han(ch) for ch in chars) or not str(reviewed or "").strip():
        return None
    toned = _letters(reviewed)
    plain = [_base(letter) for letter in toned]
    cursor = 0
    out: list[dict[str, str]] = []
    for character in chars:
        if _is_han(character):
            for expected in _candidates(character):
                end = cursor + len(expected)
                if end <= len(toned) and plain[cursor:end] == expected:
                    out.append({"char": character, "pinyin": "".join(toned[cursor:end])})
                    cursor = end
                    break
            else:
                return None
        elif character.isascii() and character.isalnum():
            if cursor >= len(plain) or plain[cursor] != character.lower():
                return None
            cursor += 1
    # Every letter of the reviewed reading must have been used: a reading longer than the
    # characters it is meant for is a different line.
    return out if cursor == len(toned) else None


def align_readings(segments: Any, readings: Mapping[str, str]) -> dict[str, list[dict[str, str]]]:
    """The per-character reading of every segment whose line and reading agree.

    `segments` are anything with `segment_id` and `original_text`; `readings` maps a
    segment id to its whole-line reading (reviewed or derived). A line that does not
    align is simply absent: the surface draws no reading for it.
    """

    result: dict[str, list[dict[str, str]]] = {}
    for segment in segments or ():
        segment_id = str(getattr(segment, "segment_id", "") or "")
        aligned = align_pinyin(str(getattr(segment, "original_text", "") or ""), str(readings.get(segment_id) or ""))
        if segment_id and aligned:
            result[segment_id] = aligned
    return result
