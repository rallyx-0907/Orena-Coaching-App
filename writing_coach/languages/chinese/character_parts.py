"""What a character is made of, as orthography facts with their provenance.

`orthography.py` in this package is explicit that it "does not infer readings,
radicals, components, or etymology; callers must supply those facts with their
own provenance". This is such a caller: curated content in
`character_parts.json`, projected into the shared orthography contract's
`radical` and `components` facts.

Two rules govern it and both are load-bearing.

**It is decomposition, not etymology.** `ORENA_VOCABULARY_ARCHITECTURE.md` §4:
"verified character etymology, modern structural decomposition, and learner
mnemonic are three different things and must be labeled as what they are". The
provenance every fact here carries says `structural-decomposition`, and the
contract's own validator is what enforces that only `etymology` may claim
trusted provenance.

**A wrong radical fails a test, not a learner.** The vendored stroke pack marks
which strokes of a character belong to its radical (`radStrokes`). So a
declared radical can be checked against verified data: the radical's own stroke
count must equal how many strokes the pack marks. `tests/test_character_parts.py`
runs that over every entry. The check caught three wrong radicals in the first
draft of the file.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parent / "character_parts.json"
EXPECTED_FORMAT = "orena.character-parts.v1"


@lru_cache(maxsize=1)
def _data() -> dict[str, Any]:
    try:
        payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"characters": {}, "provenance": {}}
    if payload.get("format") != EXPECTED_FORMAT:
        return {"characters": {}, "provenance": {}}
    return payload


def provenance() -> dict[str, str]:
    """Where these facts come from, and what kind of claim they are."""

    return dict(_data().get("provenance") or {})


def covered() -> int:
    return len(_data().get("characters") or {})


def _said(item: Mapping[str, Any], support: str) -> dict[str, Any]:
    """One part, with its gloss in the learner's support language.

    A gloss that has not been written in that language is **absent**, not the
    English one wearing another label - the rest of this room follows the same
    rule, and a learner reading Vietnamese should not be handed English and
    told it is theirs.
    """

    part = {"surface": str(item.get("surface") or "")}
    reading = str(item.get("reading") or "")
    if reading:
        part["reading"] = reading
    role = str(item.get("role") or "")
    if role:
        part["role"] = role
    gloss = str(item.get(f"gloss_{support}") or "")
    if gloss:
        part["gloss"] = gloss
    return part


def facts_for(character: str, *, support: str = "en") -> dict[str, dict[str, Any]]:
    """The `radical` and `components` facts for one character, or nothing.

    Shaped for `build_chinese_orthography(facts=...)`, which copies them into
    the unit and validates them against the shared contract.
    """

    entry = (_data().get("characters") or {}).get(str(character or ""))
    if not entry:
        return {}
    where = provenance()
    facts: dict[str, dict[str, Any]] = {}
    radical = entry.get("radical")
    if isinstance(radical, Mapping) and radical.get("surface"):
        facts["radical"] = {"value": _said(radical, support), "provenance": dict(where)}
    components = [
        _said(item, support)
        for item in entry.get("components") or ()
        if isinstance(item, Mapping) and item.get("surface")
    ]
    if components:
        facts["components"] = {"value": components, "provenance": dict(where)}
    return facts


def facts_for_word(word: str, *, support: str = "en") -> dict[str, dict[str, dict[str, Any]]]:
    """The same, for every character in a word, keyed by character."""

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for character in str(word or ""):
        if character in out:
            continue
        found = facts_for(character, support=support)
        if found:
            out[character] = found
    return out
