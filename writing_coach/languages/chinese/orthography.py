"""Chinese adapter for the shared orthography contract.

This module owns only the Chinese-specific conversion from the existing
vendored stroke provider. It does not infer readings, radicals, components, or
etymology; callers must supply those facts with their own provenance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from writing_coach.languages.chinese.stroke_order import GLYPH_SIZE, stroke_order_for
from writing_coach.orthography import validate_orthography


def _vendor_provenance() -> dict[str, str]:
    from writing_coach.languages.chinese.stroke_order import SOURCE_VERSION

    return {
        "source": "make-me-a-hanzi",
        "version": SOURCE_VERSION,
        "evidence_type": "vendored-stroke-data",
    }


def _stroke_facts(entry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    provenance = _vendor_provenance()
    return {
        "stroke_count": {
            "value": entry["stroke_count"],
            "provenance": dict(provenance),
        },
        "stroke_order": {
            "value": {
                "representation": "svg-paths",
                "glyph_size": GLYPH_SIZE,
                "paths": list(entry["stroke_paths"]),
                "medians": list(entry["medians"]),
            },
            "provenance": dict(provenance),
        },
    }


def build_chinese_orthography(
    word: str,
    *,
    readings: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    facts: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build generic orthographic units from verified Chinese stroke data.

    ``readings`` and ``facts`` are caller-supplied additions. They are copied
    into every matching unit, including repeated characters, and validated as
    contract data. The stroke provider remains authoritative for its two facts;
    missing provider data is reported in ``unavailable`` instead of guessed.
    """

    payload = stroke_order_for(word)
    reading_map = readings or {}
    fact_map = facts or {}
    units: list[dict[str, Any]] = []

    for entry in payload["characters"]:
        surface = str(entry["character"])
        supplied_facts = dict(fact_map.get(surface, {}))
        supplied_facts.pop("stroke_count", None)
        supplied_facts.pop("stroke_order", None)
        unit_facts = {**supplied_facts, **_stroke_facts(entry)}
        unit = {
            "surface": surface,
            "script": "han",
            "unit_kind": "character",
            "readings": [dict(item) for item in reading_map.get(surface, ())],
            "facts": unit_facts,
        }
        units.append(unit)

    result: dict[str, Any] = {
        "script": "han",
        "units": units,
        "unavailable": list(payload["unavailable"]),
    }
    validate_orthography(result)
    return result
