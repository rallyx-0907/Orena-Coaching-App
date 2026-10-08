"""The committed contract files: schemas, error tags, migrated sample content."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from grammar_lab.pipeline.export_error_tags import ExportError, build_error_tags, read_constant
from grammar_lab.pipeline.jsonio import read_json
from grammar_lab.pipeline.migrate_sample_v01 import SAMPLE, migrate
from grammar_lab.pipeline.validate import LAB_ROOT, validate_lang

SCHEMA = read_json(LAB_ROOT / "schema" / "grammar_set.schema.json")
INVENTORY_SCHEMA = read_json(LAB_ROOT / "schema" / "inventory.schema.json")
REPO_ROOT = LAB_ROOT.parent
SPEC_TIMELINE_KINDS = [
    "point_past", "ongoing_now", "unspecified_past", "habit", "future_condition", "future_plan", "past_ongoing",
]


@pytest.mark.parametrize("schema", [SCHEMA, INVENTORY_SCHEMA], ids=["grammar_set", "inventory"])
def test_schemas_are_valid_draft_2020_12(schema: dict) -> None:
    Draft202012Validator.check_schema(schema)


def test_level_scales_fix_one_framework_per_language() -> None:
    assert {lang: scale["framework"] for lang, scale in SCHEMA["level_scales"].items()} == {
        "en": "cefr", "zh-Hans": "hsk3", "ja": "jlpt",
    }


def _conditional_levels(schema_part: dict, discriminator: str) -> dict[str, tuple[str, list[str]]]:
    out = {}
    for rule in schema_part["allOf"]:
        condition = rule["if"]["properties"].get(discriminator)
        level = rule["then"].get("properties", {}).get("level")
        if condition and level:
            key = condition.get("const") or condition["pattern"].strip("^\\.")
            out[key] = (level["properties"]["framework"]["const"], level["properties"]["value"]["enum"])
    return out


def test_schema_level_rules_match_level_scales() -> None:
    scales = {lang: (s["framework"], s["values"]) for lang, s in SCHEMA["level_scales"].items()}
    assert _conditional_levels(SCHEMA["$defs"]["grammar_point"], "target_lang") == scales
    short = {"en": "en", "zh": "zh-Hans", "ja": "ja"}
    inventory = _conditional_levels(INVENTORY_SCHEMA["$defs"]["item"], "inv_id")
    assert {short[key]: value for key, value in inventory.items()} == scales


def test_timeline_kind_is_the_closed_spec_enum() -> None:
    assert SCHEMA["$defs"]["block_timeline"]["properties"]["kind"]["enum"] == SPEC_TIMELINE_KINDS


def test_bridge_is_not_a_storable_block() -> None:
    assert "bridge" not in SCHEMA["$defs"]["block"]["properties"]["type"]["enum"]


def test_committed_sample_validates_clean() -> None:
    report = validate_lang("en", LAB_ROOT)
    assert report.points == 10
    assert report.ok, [issue.to_dict() for issue in report.issues]


def test_migration_reproduces_committed_content(tmp_path: Path) -> None:
    shutil.copytree(LAB_ROOT / "schema", tmp_path / "schema")
    written = migrate(SAMPLE, tmp_path)
    assert len(written) == 12  # manifest + 10 points + functions
    for path in written:
        relative = path.relative_to(tmp_path)
        assert path.read_bytes() == (LAB_ROOT / relative).read_bytes(), relative


def test_migration_keeps_every_sample_point_and_pitfall() -> None:
    sample = read_json(SAMPLE)
    for old in sample["grammar_points"]:
        new = read_json(LAB_ROOT / "content" / "en" / f"{old['id']}.json")
        assert [b["type"] for b in new["blocks"]] == [b["type"] for b in old["blocks"]]
        old_pitfalls = [b for b in old["blocks"] if b["type"] == "pitfall"]
        new_pitfalls = [b for b in new["blocks"] if b["type"] == "pitfall"]
        assert [(b["wrong"], b["right"]) for b in new_pitfalls] == [(b["wrong"], b["right"]) for b in old_pitfalls]
        assert all(b["l1"] == [old_b["l1"]] for b, old_b in zip(new_pitfalls, old_pitfalls, strict=True))


def test_error_tags_file_matches_engine_sources() -> None:
    """Drift guard: schema/error_tags.json must equal a fresh export of the app's evaluator labels."""
    if not (REPO_ROOT / "writing_coach").is_dir():
        pytest.skip("app sources not available next to grammar_lab/")
    committed = read_json(LAB_ROOT / "schema" / "error_tags.json")
    fresh = build_error_tags(REPO_ROOT)
    assert committed["languages"] == fresh["languages"]
    assert committed["engine_contract"] == fresh["engine_contract"]


def test_export_reads_constants_without_importing(tmp_path: Path) -> None:
    for relative, tags in {
        "writing_coach/languages/english/profile.py": ("article", "other"),
        "writing_coach/languages/chinese/profile.py": ("particle", "other"),
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text(f"import does_not_exist\nERROR_CATEGORIES = {tags!r}\n", encoding="utf-8")
    (tmp_path / "writing_coach" / "writing_evaluation.py").write_text('EVALUATION_SCHEMA_VERSION = "v9"\n', encoding="utf-8")
    data = build_error_tags(tmp_path)
    assert data["engine_contract"] == "v9"
    assert data["languages"]["en"]["tags"] == ["article", "other"]
    assert data["languages"]["zh-Hans"]["tags"] == ["particle", "other"]


def test_export_fails_loudly_when_the_constant_is_gone(tmp_path: Path) -> None:
    path = tmp_path / "profile.py"
    path.write_text("OTHER = 1\n", encoding="utf-8")
    with pytest.raises(ExportError):
        read_constant(path, "ERROR_CATEGORIES")
