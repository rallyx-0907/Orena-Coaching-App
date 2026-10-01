"""Canonical catalog v1 -> runtime catalogue, generation selection, coverage and the UI fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from grammar_lab.pipeline.canonical import (
    canonical_dir, catalog_is_current, catalog_path, load_canonical, write_catalog,
    zh_source_coverage,
)
from grammar_lab.pipeline.content_store import load_functions, load_points
from grammar_lab.pipeline.coverage import coverage_report
from grammar_lab.pipeline.corpus import generation_items
from grammar_lab.pipeline.jsonio import format_json, read_json
from grammar_lab.pipeline.seed import apply_seed, load_catalog, load_seeds, select_ids
from grammar_lab.pipeline.ui_fixtures import DEMO_POINTS, FIXTURE_DIR, INDEX_NAME, build_fixtures
from grammar_lab.pipeline.validate import ERROR_TAGS_PATH, LAB_ROOT, LANGS
from grammar_lab.tests.conftest import Lab

EXPECTED_LEVELS = {
    "en": {"A1": 30, "A2": 38, "B1": 55, "B2": 44, "C1": 30, "C2": 18},
    "zh": {"HSK1": 43, "HSK2": 61, "HSK3": 55, "HSK4": 52, "HSK5": 51, "HSK6": 49, "HSK7": 23, "HSK8": 23, "HSK9": 23},
}
EXPECTED_TOTAL = {"en": 215, "zh": 380}
SEED_FIELDS = ("function", "point_type", "native_title", "title", "error_tags", "contrasts", "prereqs", "sequence", "anchors")


def _by_canonical_level(records: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        label = record["catalog"]["canonical_level"]
        counts[label] = counts.get(label, 0) + 1
    return counts


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_runtime_catalog_has_the_locked_counts_and_distribution(lang: str) -> None:
    records = load_catalog(lang)
    assert len(records) == EXPECTED_TOTAL[lang]
    assert _by_canonical_level(records) == EXPECTED_LEVELS[lang]
    assert len(load_canonical(lang)["items"]) == EXPECTED_TOTAL[lang]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_no_duplicate_canonical_id_or_legacy_alias(lang: str) -> None:
    records = load_catalog(lang)
    ids = [record["id"] for record in records]
    assert len(ids) == len(set(ids))
    assert all(point_id.startswith(f"{lang}.") for point_id in ids)
    aliases = [alias for record in records for alias in record["aliases"]]
    assert len(aliases) == len(set(aliases)) and aliases


def test_gf0025_source_inventory_is_covered_572_of_572() -> None:
    coverage = zh_source_coverage()
    assert coverage == {
        "total": 572, "covered": 572, "missing": [], "reciprocal_mismatches": [], "unknown_sources_in_map": [],
        "orphan_citations": [], "duplicate_source_ids": 0,
    }
    # ...and the runtime catalogue carries every source row, so coverage survives the conversion
    carried = {source for record in load_catalog("zh") for source in record.get("gf0025", [])}
    assert len(carried) == 572


def test_zh_hsk7_to_9_keep_their_internal_sequencing_metadata() -> None:
    for record in load_catalog("zh"):
        if record["catalog"]["canonical_level"] in ("HSK7", "HSK8", "HSK9"):
            assert record["catalog"]["official_band"] == "HSK7-9"
            assert record["catalog"]["level_origin"] == "orena_internal_sequence_within_official_hsk7_9"
        else:
            assert record["catalog"]["official_band"] == record["catalog"]["canonical_level"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_committed_catalog_is_exactly_what_the_importer_produces(lang: str) -> None:
    assert catalog_is_current(lang)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_importer_is_idempotent(lang: str, tmp_path: Path) -> None:
    (tmp_path / "inventory").mkdir()
    shutil.copytree(canonical_dir(LAB_ROOT), canonical_dir(tmp_path))
    shutil.copy(LAB_ROOT / "inventory" / f"seeds_{lang}.yaml", tmp_path / "inventory")
    assert write_catalog(lang, tmp_path) is True
    first = catalog_path(lang, tmp_path).read_bytes()
    assert write_catalog(lang, tmp_path) is False
    assert catalog_path(lang, tmp_path).read_bytes() == first == catalog_path(lang).read_bytes()


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_reviewed_seed_metadata_is_preserved_where_ids_overlap(lang: str) -> None:
    records = {record["id"]: record for record in load_catalog(lang)}
    seeds = load_seeds(lang)
    assert seeds
    for seed in seeds:
        record = records[seed["id"]]
        for key in SEED_FIELDS:
            assert record[key] == seed[key], (seed["id"], key)
        assert record["catalog"]["metadata_origin"] == "reviewed_seed"
        assert "seed_level_overridden" not in record["catalog"], seed["id"]  # canonical and seed levels agree
        assert sorted(record["r5"]) == sorted(seed["r5"]), seed["id"]


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_full_canonical_catalog_has_reviewed_metadata_only(lang: str) -> None:
    seeds = load_seeds(lang)
    records = load_catalog(lang)
    assert len(seeds) == EXPECTED_TOTAL[lang]
    assert {seed["id"] for seed in seeds} == {record["id"] for record in records}
    defaults = [record["id"] for record in records if record["catalog"]["metadata_origin"] == "default_safe"]
    assert defaults == [], f"{lang} still has default-safe canonical metadata: {defaults[:10]}"
    assert all(record["catalog"]["metadata_origin"] == "reviewed_seed" for record in records)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_catalog_references_stay_inside_the_catalog_and_never_point_up(lang: str) -> None:
    records = {record["id"]: record for record in load_catalog(lang)}
    order = {value: i for i, value in enumerate(["A1", "A2", "B1", "B2", "C1", "C2"] if lang == "en" else list("123456789"))}
    for record in records.values():
        for other in (*record["contrasts"], *record["prereqs"]):
            assert other in records, (record["id"], other)
        for prereq in record["prereqs"]:
            assert order[records[prereq]["level"]] <= order[record["level"]], (record["id"], prereq)


@pytest.mark.parametrize("lang,levels", [("en", EXPECTED_LEVELS["en"]), ("zh", EXPECTED_LEVELS["zh"])])
def test_generate_selection_resolves_every_level(lang: str, levels: dict[str, int]) -> None:
    everything: list[str] = []
    for label, count in levels.items():
        ids = select_ids(lang, label)
        assert len(ids) == count, label
        everything += ids
    assert sorted(everything) == sorted(record["id"] for record in load_catalog(lang))
    assert select_ids("zh", "3") == select_ids("zh", "HSK3")  # both spellings of an HSK level
    assert select_ids(lang, "Z9") == []


def test_corpus_generation_selector_can_include_existing_reviewed_points() -> None:
    plan = {
        "languages": {
            "en": {
                "items": [
                    {"id": "en.ready", "level": "A1", "status": "ready"},
                    {"id": "en.generated", "level": "A1", "status": "generated"},
                    {"id": "en.blocked", "level": "A1", "status": "blocked_metadata"},
                    {
                        "id": "en.generated_unreviewed",
                        "level": "A1",
                        "status": "generated_unreviewed_metadata",
                    },
                ]
            }
        }
    }
    assert generation_items(plan) == [("en", "A1", "en.ready")]
    assert generation_items(plan, include_generated=True) == [
        ("en", "A1", "en.ready"),
        ("en", "A1", "en.generated"),
    ]


def test_generate_level_option_reads_the_catalog_not_the_old_seed_subset() -> None:
    from grammar_lab.pipeline.cli import app
    from typer.testing import CliRunner

    # A1 is every canonical A1 point (30), whatever share of them has reviewed seeds yet.
    assert select_ids("en", "A1") == [r["id"] for r in load_catalog("en") if r["level"] == "A1"]
    assert len(select_ids("en", "A1")) == 30
    result = CliRunner().invoke(app, ["generate", "--lang", "en", "--level", "Z9"])
    assert result.exit_code != 0 and "no catalogue points at level Z9" in result.output


def test_zh_point_carries_its_gf0025_source_refs() -> None:
    record = next(r for r in load_catalog("zh") if r.get("gf0025"))
    assert apply_seed(None, "zh", record["id"])["source_refs"]["gf0025"] == record["gf0025"]


def test_coverage_separates_catalog_from_generated_content(tmp_path: Path) -> None:
    report = coverage_report("en")
    assert report["canonical_total"] == 215
    generated = len(load_points("en")) - len(report["content_outside_catalog"])
    assert report["generated_total"] == generated and 0 < generated < 215  # content on disk grows; the catalogue does not
    assert report["missing_content_total"] == 215 - generated == len(report["missing_content"])
    assert report["approved_total"] == 0 and report["auto_ok_total"] == 0  # a draft is not approved
    assert report["validated_total"] <= report["generated_total"]
    assert {label: row["canonical"] for label, row in report["per_level"].items()} == EXPECTED_LEVELS["en"]
    assert all(row["generated"] <= row["canonical"] for row in report["per_level"].values())
    zh = coverage_report("zh")
    assert zh["canonical_total"] == 380 and zh["gf0025"]["covered"] == zh["gf0025"]["total"] == 572
    assert zh["generated_total"] < zh["canonical_total"]


def test_coverage_counts_generated_validated_and_approved_apart(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.points["en.beta"]["status"] = "approved"
    lab.points["en.beta"]["review"] = {"reviewer": "t", "seconds": 1, "reviewed_at": "2026-09-30T00:00:00Z"}
    lab.write()
    (tmp_path / "inventory").mkdir(exist_ok=True)
    records = [
        {"id": point_id, "level": level, "function": "fn.alpha"}
        for point_id, level in (("en.alpha", "A1"), ("en.beta", "A2"), ("en.gamma", "A2"))
    ]
    (tmp_path / "inventory" / "seeds_en.yaml").write_text(yaml.safe_dump(records), encoding="utf-8")
    report = coverage_report("en", tmp_path)
    assert report["canonical_total"] == 3 and report["generated_total"] == 2
    assert report["missing_content"] == ["en.gamma"]  # in the catalogue, not written
    assert report["approved_total"] == 1
    assert report["per_level"]["A2"] == {"canonical": 2, "generated": 1, "validated": report["per_level"]["A2"]["validated"],
                                         "auto_ok": 0, "approved": 1}


# --- UI fixtures -------------------------------------------------------------------------------------


def _fixture(lang: str) -> dict:
    return read_json(LAB_ROOT / FIXTURE_DIR / f"{DEMO_POINTS[lang]}.json")


def test_committed_ui_fixtures_are_what_the_builder_produces() -> None:
    for name, value in build_fixtures().items():
        assert (LAB_ROOT / FIXTURE_DIR / name).read_text(encoding="utf-8") == format_json(value), name


def test_zh_fixture_ruby_pinyin_is_per_character_and_aligned() -> None:
    point = _fixture("zh")
    strings = [(example["text"], example["pinyin"]) for example in point["examples"]]
    strings += [(m["wrong"], m["wrong_pinyin"]) for m in point["common_mistakes"]]
    strings += [(m["right"], m["right_pinyin"]) for m in point["common_mistakes"]]
    strings += [(slot["text"], slot["pinyin"]) for slot in point["pattern"]["formula"]]
    strings += [(item["q"].replace("___", ""), None) for item in point["quick_practice"]]
    checked = 0
    for text, pinyin in strings:
        if pinyin is None:
            continue
        assert len(pinyin) == len(text), text
        for char, syllable in zip(text, pinyin, strict=True):
            assert (syllable == "") == (not "一" <= char <= "鿿"), (text, char, syllable)
            assert not any(ch.isdigit() for ch in syllable)  # tone marks, never tone numbers
        checked += 1
    assert checked >= 8


def test_fixtures_exercise_most_of_the_contract_and_say_what_they_do_not() -> None:
    index = read_json(LAB_ROOT / FIXTURE_DIR / INDEX_NAME)
    used = {name for entry in index["fixtures"] for name in entry["primitives"]}
    assert {"pattern.formula", "pattern.formula.optional", "pattern.variants.negative", "pattern.variants.question",
            "pattern.illustration.timeline", "examples.spans", "examples.pinyin", "compare", "common_mistakes",
            "common_mistakes.pinyin", "quick_practice", "personal_production"} <= used
    assert set(index["not_covered_by_these_two"]).isdisjoint(used)
    assert "blocks.story" in index["not_covered_by_these_two"]  # story is paused on v0.4: not faked
    assert all(entry["generation"] == "reference_fixture" and entry["provider_calls_for_this_fixture"] == 0
               for entry in index["fixtures"])
