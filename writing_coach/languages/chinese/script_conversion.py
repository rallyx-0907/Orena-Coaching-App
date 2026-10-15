"""Convert Chinese text to one script, character by character (D-207, PROPOSED).

Pure and deterministic: no network, no AI, no dependency. The table (`script_map.json`) is derived from the
vendored CC-CEDICT pack by `scripts/build_chinese_script_table.py` and holds only characters whose conversion is
unambiguous in the dictionary. Every mapping is one character to one character, so a converted text keeps its
length and a word timing or tap offset computed before conversion still lines up after it.

Limits, stated so no caller assumes more:

* Traditional to Simplified is complete for the characters the dictionary lists (the forms are many to one).
* Simplified to Traditional skips a Simplified character with more than one Traditional form (发 is 發 or 髮,
  后 is 後 or 后): it is left as written. It is a character-level conversion, not a regional-vocabulary one.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from writing_coach.languages.chinese.script_detection import SIMPLIFIED, TRADITIONAL

MAP_PATH = Path(__file__).resolve().parent / "script_map.json"


@lru_cache(maxsize=1)
def _tables() -> tuple[dict[int, str], dict[int, str]]:
    try:
        data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
        return (
            {ord(key): value for key, value in data["to_simplified"].items()},
            {ord(key): value for key, value in data["to_traditional"].items()},
        )
    except (OSError, ValueError, KeyError):
        return {}, {}


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
    to_simplified, to_traditional = _tables()
    return str(text or "").translate(to_traditional if target == TRADITIONAL else to_simplified)
