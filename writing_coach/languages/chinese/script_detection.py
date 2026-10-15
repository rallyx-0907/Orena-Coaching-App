"""Which Chinese script a text is written in: Simplified, Traditional, mixed, or too little to tell (D-197, PROPOSED).

Pure and deterministic: no network, no AI, no dependency. The evidence is character-level. A Chinese text is
mostly characters both scripts share; the ones that tell the scripts apart are those that exist in only one. The
table of those (`script_chars.json`) is derived from the vendored CC-CEDICT pack by
`scripts/build_chinese_script_table.py`, so it can be rebuilt and checked against the pack.

Thresholds, all in this file:

* `MIN_EVIDENCE` (15): fewer script-specific characters than this is `unknown`. A real article of a few hundred
  Hanzi carries dozens (about one character in four is script-specific); a headline, a caption or a snippet does
  not carry enough to say, and a wrong label is worse than none.
* `NOISE_SHARE` (0.10): the share of the minority script tolerated before the text is called `mixed`. A
  Simplified text legitimately quotes a Traditional name or title (a few characters), and a Traditional text a
  Simplified one; the dictionary also records a few characters as one script that the other script borrows.
  At or under 10 percent of the evidence the majority script wins; above it, the text mixes the two.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

SIMPLIFIED = "zh-Hans"
TRADITIONAL = "zh-Hant"
MIXED = "mixed"
UNKNOWN = "unknown"
SCRIPTS = (SIMPLIFIED, TRADITIONAL, MIXED, UNKNOWN)

MIN_EVIDENCE = 15
NOISE_SHARE = 0.10

TABLE_PATH = Path(__file__).resolve().parent / "script_chars.json"


@lru_cache(maxsize=1)
def _table() -> tuple[frozenset[str], frozenset[str]]:
    try:
        data = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
        return frozenset(str(data["simplified"])), frozenset(str(data["traditional"]))
    except (OSError, ValueError, KeyError):
        return frozenset(), frozenset()


def is_traditional_only(char: str) -> bool:
    """Whether the character exists only in Traditional writing (evidence that the text around it is Traditional)."""
    return char in _table()[1]


def script_counts(text: str) -> tuple[int, int]:
    """(simplified-only characters, traditional-only characters) in the text."""
    simplified, traditional = _table()
    s = t = 0
    for char in text or "":
        if char in simplified:
            s += 1
        elif char in traditional:
            t += 1
    return s, t


def detect_script(text: str) -> str:
    """`zh-Hans`, `zh-Hant`, `mixed` or `unknown` for a Chinese text."""
    s, t = script_counts(text)
    evidence = s + t
    if evidence < MIN_EVIDENCE:
        return UNKNOWN
    if t / evidence <= NOISE_SHARE:
        return SIMPLIFIED
    if s / evidence <= NOISE_SHARE:
        return TRADITIONAL
    return MIXED
