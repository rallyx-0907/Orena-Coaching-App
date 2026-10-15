"""Convert Chinese text to one script, character by character (D-208, PROPOSED).

Pure and deterministic: no network, no AI, no dependency. The table (`script_map.json`) is derived from the
vendored CC-CEDICT pack by `scripts/build_chinese_script_table.py` and holds only characters whose conversion is
unambiguous in the dictionary. Every mapping is one character to one character, so a converted text keeps its
length and a word timing or tap offset computed before conversion still lines up after it.

Traditional to Simplified has two layers (D-211):

* a one-to-one table: a Traditional-only character with one Simplified form, from CC-CEDICT, plus the characters
  for which the Unicode Unihan `kSimplifiedVariant` field names exactly one (麼 is 么; CC-CEDICT also lists the
  variant 麽, so it alone could not choose);
* a context table for the characters whose Simplified form depends on the word, used only near Traditional
  evidence: a clause with no Traditional-only character within 30 characters is never touched by it, so genuine
  Simplified text (鲁迅著, 乾卦, 宫商角徵羽, 覆水) is returned as written. 著 is 着 in 看著 and stays 著 in
  著名; 乾 is 干 in 乾淨 and stays 乾 in 乾坤. The default is the form CC-CEDICT writes most often for that
  Traditional character, and the Simplified words of CC-CEDICT that contain the character (2 to 4 characters) are
  kept as written. The choice is made on the converted text, so 顯著 (显著) is found by its Simplified spelling.

Limits, stated so no caller assumes more:

* A context-dependent character is judged by the words of the dictionary only. A word it does not list takes the
  default (a rare proper name with 乾 or 著 can be changed); `unresolved` in the table lists the Unihan characters
  with no evidence for a choice, which are left as written.
* Simplified to Traditional skips a Simplified character with more than one Traditional form (发 is 發 or 髮,
  后 is 後 or 后): it is left as written. It is a character-level conversion, not a regional-vocabulary one.
"""
from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

from writing_coach.languages.chinese.script_detection import SIMPLIFIED, TRADITIONAL

MAP_PATH = Path(__file__).resolve().parent / "script_map.json"
KEEP_WORD_MAX = 4  # the longest kept word in the table (scripts/build_chinese_script_table.py)


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[int, str], dict[int, str], dict[str, tuple[str, frozenset[str]]]]:
    try:
        data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        return (
            {ord(key): value for key, value in data["to_simplified"].items()},
            {ord(key): value for key, value in data["to_traditional"].items()},
            {
                key: (str(item["to"]), frozenset(item.get("keep") or ()))
                for key, item in (data.get("contextual_to_simplified") or {}).items()
            },
        )
    except (OSError, ValueError, KeyError, TypeError):
        return {}, {}, {}


# A context-dependent character is judged only near Traditional evidence (D-211): Simplified text is never altered
# by it (鲁迅著 stays, 乾卦 stays). "Near" is the same clause and within this many characters of a Traditional-only one.
EVIDENCE_REACH = 30
_CLAUSE_BREAKS = frozenset("，。！？；：、,.!?;:" + chr(10))


def _contextual(text: str, original: str, table: dict[str, tuple[str, frozenset[str]]]) -> str:
    """Each context-dependent character written as its default Simplified form unless it sits inside a word that is
    Simplified as written, and only where `original` (the text before any conversion, same length) shows Traditional
    evidence nearby. One character in, one character out."""
    if not any(char in table for char in text):
        return text
    from writing_coach.languages.chinese.script_detection import is_traditional_only

    clause, number = [], 0
    for char in original:
        if char in _CLAUSE_BREAKS:
            number += 1
        clause.append(number)
    evidence = [index for index, char in enumerate(original) if is_traditional_only(char)]
    if not evidence:
        return text
    out = list(text)
    for index, char in enumerate(text):
        entry = table.get(char)
        if entry is None:
            continue
        if not any(clause[j] == clause[index] and abs(j - index) <= EVIDENCE_REACH for j in evidence):
            continue
        target, keep = entry
        protected = any(
            text[start:start + size] in keep
            for size in range(2, KEEP_WORD_MAX + 1)
            for start in range(max(0, index - size + 1), min(index, len(text) - size) + 1)
        )
        if not protected:
            out[index] = target
    return "".join(out)


@lru_cache(maxsize=1)
def _compatibility() -> dict[int, str]:
    """Compatibility ideographs (U+F900 to U+FAFF, U+2F800 to U+2FA1F) written as the unified ideograph they stand
    for. Each NFC form is exactly one code point, so a text keeps its length; any that is not is left out."""
    table: dict[int, str] = {}
    for low, high in ((0xF900, 0xFB00), (0x2F800, 0x2FA20)):
        for code in range(low, high):
            normal = unicodedata.normalize("NFC", chr(code))
            if len(normal) == 1 and normal != chr(code):
                table[code] = normal
    return table


def target_script(language: str) -> str:
    """The script a language tag asks for: `zh-Hant`, `zh-TW`, `zh-HK` or `zh-MO` is Traditional; everything else
    that is Chinese (`zh`, `zh-CN`, `zh-Hans`, `cmn`) is Simplified, the default."""
    tag = str(language or "").strip().replace("_", "-").casefold()
    parts = tag.split("-")[1:]
    if "hant" in parts or any(part in {"tw", "hk", "mo"} for part in parts):
        return TRADITIONAL
    return SIMPLIFIED


def convert_script(text: str, target: str) -> str:
    """The text with every character that has an unambiguous counterpart written in the target script."""
    to_simplified, to_traditional, contextual = _tables()
    original = str(text or "").translate(_compatibility())
    if target == TRADITIONAL:
        return original.translate(to_traditional)
    return _contextual(original.translate(to_simplified), original, contextual)


def convert_sequence(parts: list[str], target: str) -> list[str]:
    """Several pieces of one running text (a recogniser's words) converted together, so a word split across two
    pieces is still seen whole, and returned as pieces of the same lengths."""
    joined = convert_script("".join(parts), target)
    if len(joined) != sum(len(part) for part in parts):
        return [convert_script(part, target) for part in parts]
    out, at = [], 0
    for part in parts:
        out.append(joined[at:at + len(part)])
        at += len(part)
    return out
