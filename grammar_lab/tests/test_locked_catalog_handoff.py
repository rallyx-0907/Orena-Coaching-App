from __future__ import annotations

from pathlib import Path

import yaml

from grammar_lab.pipeline.generate import _catalogue_scope_suffix
from grammar_lab.pipeline.seed import apply_seed, check_seeds, load_seeds
from grammar_lab.pipeline.validate import LAB_ROOT


def _ids(seeds: list[dict]) -> set[str]:
    return {seed["id"] for seed in seeds}


def test_locked_seed_catalog_counts_ids_and_references() -> None:
    en = load_seeds("en")
    zh = load_seeds("zh")
    assert len(en) == 215
    assert len(zh) == 416
    assert len(_ids(en)) == 215
    assert len(_ids(zh)) == 416
    assert all(seed["id"].startswith("en.") for seed in en)
    assert all(seed["id"].startswith("zh.") for seed in zh)
    assert {str(seed["level"]) for seed in en} == {"A1", "A2", "B1", "B2", "C1", "C2"}
    assert {str(seed["level"]) for seed in zh} == {str(i) for i in range(1, 10)}
    assert check_seeds("en") == []
    assert check_seeds("zh") == []


def test_locked_zh_seeds_cover_all_gf0025_source_rows() -> None:
    zh = load_seeds("zh")
    covered = {
        code
        for seed in zh
        for code in (seed.get("source_refs") or {}).get("hsk3", [])
    }
    source_file = LAB_ROOT.parent / "research" / "grammar_catalog" / "source_inventory_zh_gf0025.yaml"
    source = yaml.safe_load(source_file.read_text(encoding="utf-8"))
    official = {item["source_id"] for item in source["items"]}
    assert len(official) == 572
    assert covered == official


def test_apply_seed_carries_locked_hsk_source_refs() -> None:
    point_id = "zh.canon.gf.hsk1.a_1_1_1.p1"
    point = apply_seed(None, "zh", point_id, LAB_ROOT)
    assert point is not None
    assert point["source_refs"]["hsk3"] == ["gf0025.hsk1.001"]


def test_catalogue_scope_is_injected_as_generation_constraint() -> None:
    suffix = _catalogue_scope_suffix({"source_scope": ["能愿动词：想、要", "疑问句"]})
    assert "Authoritative catalogue scope" in suffix
    assert "能愿动词：想、要" in suffix
    assert "疑问句" in suffix
    assert _catalogue_scope_suffix({}) == ""


def test_locked_catalog_files_are_marked_for_generation() -> None:
    root = LAB_ROOT.parent / "research" / "grammar_catalog"
    en = yaml.safe_load((root / "canonical_grammar_en.yaml").read_text(encoding="utf-8"))
    zh = yaml.safe_load((root / "canonical_grammar_zh.yaml").read_text(encoding="utf-8"))
    assert en["meta"]["status"] == "locked_for_generation"
    assert zh["meta"]["status"] == "locked_for_generation"
    assert en["meta"]["canonical_point_count"] == 215
    assert zh["meta"]["canonical_point_count"] == 416
    assert zh["meta"]["source_coverage"] == "572/572"
