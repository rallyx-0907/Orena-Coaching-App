"""One-off upgrade of docs/grammar_lab/sample_v0.1.json to schema v0.2.

Writes content/en/_set.json, one content/en/<id>.json per grammar point and
functions/functions.yaml. Kept for audit; re-running gives identical output.
The v0.1 dotted error tags are not engine labels, so each pitfall is mapped to
the writing evaluator's closed English list (schema/error_tags.json); the
mapping and its rationale are recorded in docs/grammar_lab/PHASE0_DECISIONS.md.

    python -m grammar_lab.pipeline.migrate_sample_v01
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from grammar_lab.pipeline.jsonio import read_json, write_json
from grammar_lab.pipeline.validate import LAB_ROOT, LANGS

SAMPLE = LAB_ROOT.parent / "docs" / "grammar_lab" / "sample_v0.1.json"
SAMPLE_REF = "docs/grammar_lab/sample_v0.1.json"
MIGRATED_AT = "2026-09-26T00:00:00+07:00"
BCP47 = {"en": "en", "zh": "zh-Hans", "ja": "ja"}

# (point id) -> engine error label per pitfall, in block order.
PITFALL_TAGS: dict[str, list[str]] = {
    "en.present_simple.third_person_s": ["agreement", "agreement"],
    "en.there_is_are": ["sentence_structure", "agreement"],
    "en.plural_nouns.regular": ["agreement", "agreement"],
    "en.articles.a_an_the": ["article", "article"],
    "en.present_continuous.now": ["tense", "tense"],
    "en.past_simple": ["tense", "tense"],
    "en.present_perfect.experience": ["tense", "word_choice"],
    "en.countable_uncountable.much_many": ["word_form", "word_choice"],
    "en.comparatives": ["word_form", "sentence_structure"],
    "en.conditional_first": ["tense", "tense"],
}


def _split_realizations(realizations: dict[str, list[str]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    done: dict[str, list[str]] = {}
    planned: dict[str, list[str]] = {}
    for short, ids in realizations.items():
        for raw in ids:
            target = planned if raw.endswith("(planned)") else done
            target.setdefault(BCP47[short], []).append(raw.removesuffix("(planned)").strip())
    return done, planned


def migrate_function(function: dict[str, Any]) -> dict[str, Any]:
    done, planned = _split_realizations(function["realizations"])
    out: dict[str, Any] = {"id": function["id"], "title": function["title"], "realizations": done}
    if planned:
        out["planned"] = planned
    return out


def migrate_block(block: dict[str, Any], locale: str, pitfall_tags: list[str]) -> dict[str, Any]:
    kind = block["type"]
    if kind == "rule_table":
        return {"type": kind, "rows": [[base, derived, {locale: note}] for base, derived, note in block["rows"]]}
    if kind == "example":
        out = {key: value for key, value in block.items() if key != "ruby"}
        if block.get("ruby") is not None:
            out["ruby"] = block["ruby"]
        return out
    if kind == "pitfall":
        return {
            "type": kind,
            "l1": [block["l1"]],
            "wrong": block["wrong"],
            "right": block["right"],
            "error_tag": pitfall_tags.pop(0),
            "why": block["why"],
        }
    return dict(block)


def migrate_point(point: dict[str, Any], locale: str, scale: list[str]) -> dict[str, Any]:
    pitfall_tags = list(PITFALL_TAGS[point["id"]])
    blocks = [migrate_block(block, locale, pitfall_tags) for block in point["blocks"]]
    if pitfall_tags:
        raise ValueError(f"{point['id']}: unused pitfall tag mapping {pitfall_tags}")
    level = point["level"]
    return {
        "schema_version": "0.2",
        "id": point["id"],
        "version": 1,
        "target_lang": point["target_lang"],
        "function": point["function"],
        "level": {"framework": level["framework"], "value": level["value"], "rank": scale.index(level["value"]) + 1},
        "prereqs": point["prereqs"],
        "contrasts": point["contrasts"],
        "error_tags": list(dict.fromkeys(b["error_tag"] for b in blocks if b["type"] == "pitfall")),
        "source_refs": {},
        "title": point["title"],
        "summary": point["summary"],
        "blocks": blocks,
        "status": point["status"],
        "provenance": {
            "model": "unknown",
            "prompt_version": "sample_v0.1",
            "run_id": "migrate.sample_v0.1",
            "generated_at": MIGRATED_AT,
            "migrated_from": {"file": SAMPLE_REF, "schema_version": "0.1"},
        },
        "review": None,
    }


def migrate(sample: Path = SAMPLE, root: Path = LAB_ROOT) -> list[Path]:
    data = read_json(sample)
    meta = data["meta"]
    lang = next(short for short, bcp in LANGS.items() if bcp == meta["target_lang"])
    locale = meta["explanation_locales"][0]
    schema = read_json(root / "schema" / "grammar_set.schema.json")
    scale = schema["level_scales"][meta["target_lang"]]["values"]
    written = []

    manifest = {
        "schema_version": "0.2",
        "set_id": f"{lang}.core",
        "target_lang": meta["target_lang"],
        "explanation_locales": meta["explanation_locales"],
        "l1": meta["l1"],
        "note": f"Upgraded from {SAMPLE_REF}. All points are AI drafts awaiting review.",
    }
    manifest_path = root / "content" / lang / "_set.json"
    write_json(manifest_path, manifest)
    written.append(manifest_path)

    for point in data["grammar_points"]:
        path = root / "content" / lang / f"{point['id']}.json"
        write_json(path, migrate_point(point, locale, scale))
        written.append(path)

    functions = {"schema_version": "0.2", "functions": [migrate_function(f) for f in data["functions"]]}
    functions_path = root / "functions" / "functions.yaml"
    header = "# Communicative functions shared by every target language (SPEC §3).\n"
    body = yaml.safe_dump(functions, allow_unicode=True, sort_keys=False, width=100)
    functions_path.parent.mkdir(parents=True, exist_ok=True)
    functions_path.write_text(header + body, encoding="utf-8", newline="\n")
    written.append(functions_path)
    return written


if __name__ == "__main__":
    for path in migrate():
        print(path.relative_to(LAB_ROOT).as_posix())  # noqa: T201
