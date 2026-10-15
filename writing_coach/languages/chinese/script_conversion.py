"""Convert Chinese text to one script, character by character (D-208, PROPOSED).

Pure and deterministic: no network, no AI, no dependency. The table (`script_map.json`) is derived from the
vendored CC-CEDICT pack by `scripts/build_chinese_script_table.py` and holds only characters whose conversion is
unambiguous in the dictionary. Every mapping is one character to one character, so a converted text keeps its
length and a word timing or tap offset computed before conversion still lines up after it.

Traditional to Simplified has two layers (D-211):

* a one-to-one table: a Traditional-only character with one Simplified form, from CC-CEDICT, plus the characters
  for which the Unicode Unihan `kSimplifiedVariant` field names exactly one (麼 is 么; CC-CEDICT also lists the
  variant 麽, so it alone could not choose);
* a context table for the characters whose Simplified form depends on the word. 著 is 着 in 看著 and stays 著 in
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


def _contextual(text: str, table: dict[str, tuple[str, frozenset[str]]]) -> str:
    """Each context-dependent character written as its default Simplified form unless it sits inside a word that is
    Simplified as written. One character in, one character out."""
    if not any(char in table for char in text):
        return text
    out = list(text)
    for index, char in enumerate(text):
        entry = table.get(char)
        if entry is None:
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
    if target == TRADITIONAL:
        return str(text or "").translate(to_traditional)
    return _contextual(str(text or "").translate(to_simplified), contextual)


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
