"""Reference fixtures for the learner UI renderer: ``fixtures/ui/`` (schema v0.4).

Two complete grammar points -- one English (A1), one Chinese (HSK1) -- so the renderer can be built from
``schema + EN demo + ZH demo`` without reading R5 or the canonical research. They are the point files
already on disk, re-seeded through the runtime catalogue so their metadata (level, function, aliases,
source refs, anchors, sequence) is what the catalogue says today. Content and provenance are untouched:
nothing here calls a provider, and ``index.json`` says so.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.jsonio import format_json, write_json
from grammar_lab.pipeline.seed import apply_seed
from grammar_lab.pipeline.validate import LAB_ROOT

DEMO_POINTS = {"en": "en.present_continuous.now", "zh": "zh.le_completion"}
FIXTURE_DIR = Path("fixtures") / "ui"
INDEX_NAME = "index.json"


def fixture_dir(root: Path = LAB_ROOT) -> Path:
    return root / FIXTURE_DIR


def primitives(point: dict[str, Any]) -> list[str]:
    """The closed primitives of the v0.4 contract this point actually carries."""
    pattern = point["pattern"]
    found = ["header", "when_to_use", "pattern.formula"]
    formula_slots = pattern["formula"] + [slot for variant in pattern.get("variants", {}).values() for slot in variant]
    if any(slot.get("optional") for slot in formula_slots):
        found.append("pattern.formula.optional")
    if any("options" in slot for slot in formula_slots):
        found.append("pattern.formula.options")
    found += [f"pattern.variants.{name}" for name in pattern.get("variants", {})]
    found.append(f"pattern.illustration.{pattern['illustration']['kind']}")
    found += ["examples", "examples.spans", "examples.annotation", "examples.translation"]
    if any("pinyin" in example for example in point["examples"]):
        found.append("examples.pinyin")
    for key in ("compare", "common_mistakes", "quick_practice", "personal_production"):
        if point.get(key):
            found.append(key)
    if any("wrong_pinyin" in mistake for mistake in point["common_mistakes"]):
        found.append("common_mistakes.pinyin")
    if point.get("blocks"):
        found += [f"blocks.{block['type']}" for block in point["blocks"]]
    return found


def build_fixtures(root: Path = LAB_ROOT) -> dict[str, Any]:
    """``{file name: json value}`` for the two points and the index. Pure function of content + catalogue."""
    files: dict[str, Any] = {}
    entries: list[dict[str, Any]] = []
    for lang, point_id in DEMO_POINTS.items():
        existing = load_point(lang, point_id, root)
        if existing is None:
            raise FileNotFoundError(f"demo point {point_id} is not in content/{lang}/")
        point = apply_seed(existing, lang, point_id, root)
        files[f"{point_id}.json"] = point
        entries.append({
            "id": point_id,
            "lang": lang,
            "target_lang": point["target_lang"],
            "level": point["level"],
            "point_type": point["point_type"],
            "file": f"{point_id}.json",
            "content_source": f"content/{lang}/{point_id}.json",
            "generation": "reference_fixture",
            "provider_calls_for_this_fixture": 0,
            "content_provenance": point["provenance"],
            "primitives": primitives(point),
        })
    files[INDEX_NAME] = {
        "kind": "grammar_lab_ui_fixtures",
        "schema_version": "0.4",
        "schema": "schema/grammar_set.schema.json",
        "contract": "docs/grammar_lab/GRAMMAR_CONTENT_CONTRACT.md",
        "note": "Reference fixtures for building the renderer; status draft_ai, not reviewed learner content.",
        "fixtures": entries,
        "not_covered_by_these_two": sorted(
            {"pattern.formula.options", "pattern.illustration.morphology", "pattern.illustration.word_order", "blocks.story"}
            - {name for entry in entries for name in entry["primitives"]}
        ),
    }
    return files


def write_fixtures(root: Path = LAB_ROOT) -> bool:
    """Write ``fixtures/ui/``; returns whether anything changed (idempotent)."""
    directory = fixture_dir(root)
    changed = False
    for name, value in build_fixtures(root).items():
        path = directory / name
        if path.exists() and path.read_text(encoding="utf-8") == format_json(value):
            continue
        write_json(path, value)
        changed = True
    return changed
