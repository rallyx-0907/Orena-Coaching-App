"""Reference fixtures for the learner UI renderer: ``fixtures/ui/`` (schema v0.4), in the shape the
merged Grammar Content Contract on ``codex/work`` reads.

Two complete grammar points -- one English (A1), one Chinese (HSK1) -- so the renderer can be built from
``schema + EN demo + ZH demo`` without reading R5 or the canonical research. They are the point files
already on disk, re-seeded through the runtime catalogue so their metadata (level, function, aliases,
source refs, anchors, sequence) is what the catalogue says today. Nothing here calls a provider.

Internally Grammar Lab says ``zh-Hans`` (``target_lang`` and locale keys) and requires ``en`` only at
``approved``. The contract merged on codex/work says ``zh`` for both and requires ``vi`` + ``en`` in every
locale map at every status. The export normalises explicitly (``to_codex_export``) and is reversible
(``from_codex_export``), so the mapping is tested, not assumed. Where ``en`` does not exist in the
source content the export copies ``vi`` into it as a *declared placeholder* (paths listed in
``index.json``); no translation is invented, and a fixture with placeholders is never production-ready.
Fixtures stay ``draft_ai``: only ``approved`` points may reach learners, and these are a dev/visual
reference harness input, not a learner feed.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from grammar_lab.pipeline.content_store import load_point
from grammar_lab.pipeline.jsonio import format_json, write_json
from grammar_lab.pipeline.seed import apply_seed
from grammar_lab.pipeline.validate import LAB_ROOT, _locale_maps

DEMO_POINTS = {"en": "en.present_continuous.now", "zh": "zh.le_completion"}
FIXTURE_DIR = Path("fixtures") / "ui"
INDEX_NAME = "index.json"
# The merged contract (origin/codex/work:docs/project/GRAMMAR_CONTENT_CONTRACT.md): target_lang en | zh, locale
# maps {vi, en, zh}, vi and en both required in every map at every status.
CODEX_TARGET_LANG = {"en": "en", "zh-Hans": "zh"}
CODEX_LOCALE_KEY = {"zh-Hans": "zh"}
CODEX_REQUIRED_LOCALES = ("vi", "en")
CODEX_CONTRACT_SOURCE = "origin/codex/work:docs/project/GRAMMAR_CONTENT_CONTRACT.md"
FEED_RULE = "dev/visual/reference harness input only; never a learner production feed (only status approved reaches the UI)"


def to_codex_export(point: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """The point as codex/work reads it, plus the locale-map paths whose ``en`` is a copy of ``vi``."""
    out = copy.deepcopy(point)
    # metadata_stale is a Grammar Lab resume marker, not learner/UI content.
    # Reference fixtures stay stable while the source draft is queued for
    # regeneration after curriculum metadata changes.
    if isinstance(out.get("provenance"), dict):
        out["provenance"].pop("metadata_stale", None)
    placeholders: list[str] = []
    for path, mapping in _locale_maps(out):
        for internal, codex in CODEX_LOCALE_KEY.items():
            if internal in mapping:
                mapping[codex] = mapping.pop(internal)
        if "en" not in mapping:
            mapping["en"] = mapping["vi"]
            placeholders.append(path)
    out["target_lang"] = CODEX_TARGET_LANG[out["target_lang"]]
    return out, placeholders


def from_codex_export(export: dict[str, Any], placeholders: list[str]) -> dict[str, Any]:
    """Inverse of ``to_codex_export``: Grammar Lab's own shape, for checking against its own schema."""
    out = copy.deepcopy(export)
    back = {codex: internal for internal, codex in CODEX_LOCALE_KEY.items()}
    for path, mapping in _locale_maps(out):
        if path in placeholders:
            del mapping["en"]
        for codex, internal in back.items():
            if codex in mapping:
                mapping[internal] = mapping.pop(codex)
    out["target_lang"] = {codex: internal for internal, codex in CODEX_TARGET_LANG.items()}[out["target_lang"]]
    return out


def locale_gaps(point: dict[str, Any], required: tuple[str, ...] = CODEX_REQUIRED_LOCALES) -> list[str]:
    """Paths of locale maps missing a required locale (what the merged contract's ``locale.missing`` reports)."""
    return [path for path, mapping in _locale_maps(point) if any(key not in mapping for key in required)]


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
        internal = apply_seed(existing, lang, point_id, root)
        point, placeholders = to_codex_export(internal)
        files[f"{point_id}.json"] = point
        entries.append({
            "id": point_id,
            "lang": lang,
            "target_lang": point["target_lang"],
            "status": point["status"],
            "production_ready": not placeholders and point["status"] == "approved",
            "en_placeholder_paths": placeholders,
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
        "feed": FEED_RULE,
        "learner_production_feed": False,
        "codex_contract": {
            "source": CODEX_CONTRACT_SOURCE,
            "target_lang": CODEX_TARGET_LANG,
            "locale_key_rename": CODEX_LOCALE_KEY,
            "locales_required_in_every_map": list(CODEX_REQUIRED_LOCALES),
            "en_placeholder": "where the source content has no en, en is a copy of vi (declared per fixture in "
                              "en_placeholder_paths); no translation was generated",
        },
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
