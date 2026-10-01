"""The catalogue seeds (inventory/seeds_<lang>.yaml) and generate-from-seed (human, 2026-09-29)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from grammar_lab.pipeline.content_store import load_functions, load_points
from grammar_lab.pipeline.generate import Generator
from grammar_lab.pipeline.jsonio import read_json
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.pipeline.r5_source import load_r5
from grammar_lab.pipeline.seed import audit_seed_semantics, aliases_for, apply_seed, check_seeds, load_seeds, register_realization
from grammar_lab.pipeline.validate import ERROR_TAGS_PATH, GRAMMAR_SCHEMA_PATH, LAB_ROOT, LANGS, validate_lang
from grammar_lab.tests.conftest import Lab
from grammar_lab.tests.test_generate import CANNED_V04, v04_transport

ORDER = {"en": ["A1", "A2", "B1", "B2", "C1", "C2"], "zh": ["1", "2", "3", "4", "5", "6", "7", "8", "9"]}
# Points kept on disk that no seed covers yet: their rows wait for the catalogue lock.
NOT_SEEDED = {"en.past_simple", "zh.ba_construction"}
# Drafts on disk whose level the seed corrects (the R5 lesson and Core Inventory item both say A1 / A2): the
# next generate re-seeds them.
RELEVELED = {"en.articles.the", "en.conditional_first"}


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_seed_file_is_internally_consistent(lang: str) -> None:
    assert check_seeds(lang) == []


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_every_seed_points_at_things_that_exist(lang: str) -> None:
    seeds = load_seeds(lang)
    assert seeds
    functions = {f["id"]: f for f in load_functions()["functions"]}
    engine_tags = set(read_json(LAB_ROOT / ERROR_TAGS_PATH)["languages"][LANGS[lang]]["tags"])
    r5 = load_r5(lang)
    core_inventory = {(r["code"], r["level"]) for r in csv.DictReader(
        (LAB_ROOT / "inventory" / "raw" / "core_inventory_en.csv").open(encoding="utf-8"))}
    scale = read_json(LAB_ROOT / GRAMMAR_SCHEMA_PATH)["level_scales"][LANGS[lang]]["values"]
    for seed in seeds:
        assert seed["id"].startswith(f"{lang}."), seed["id"]
        assert seed["function"] in functions, seed["id"]
        listed = functions[seed["function"]].get("realizations", {}).get(LANGS[lang], []) + \
            functions[seed["function"]].get("planned", {}).get(LANGS[lang], [])
        assert seed["id"] in listed, f"{seed['id']} is in neither realizations nor planned of {seed['function']}"
        assert set(seed["error_tags"]) <= engine_tags and seed["error_tags"], seed["id"]
        assert str(seed["level"]) in scale
        assert set(seed["r5"]) <= set(r5), (seed["id"], sorted(set(seed["r5"]) - set(r5)))
        for anchor in seed["anchors"]:
            assert (anchor["code"], anchor["level"]) in core_inventory, (seed["id"], anchor)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_each_seed_has_exactly_one_function_owner(lang: str) -> None:
    lang_key = LANGS[lang]
    functions = load_functions()["functions"]
    owners: dict[str, list[str]] = {}
    for function in functions:
        for section in ("realizations", "planned"):
            for point_id in function.get(section, {}).get(lang_key, []):
                owners.setdefault(point_id, []).append(function["id"])
    for seed in load_seeds(lang):
        assert owners.get(seed["id"]) == [seed["function"]], (
            seed["id"], seed["function"], owners.get(seed["id"], [])
        )



@pytest.mark.parametrize("lang", ["en", "zh"])
def test_prereqs_never_point_up_and_sequence_is_unique_per_group(lang: str) -> None:
    seeds = load_seeds(lang)
    by_id = {s["id"]: s for s in seeds}
    rank = {value: i for i, value in enumerate(ORDER[lang])}
    groups: dict[tuple[str, str], list[int]] = {}
    for seed in seeds:
        groups.setdefault((seed["function"], str(seed["level"])), []).append(seed["sequence"])
        for prereq in seed["prereqs"]:
            assert rank[str(by_id[prereq]["level"])] <= rank[str(seed["level"])], (seed["id"], prereq)
    for key, sequences in groups.items():
        assert sorted(sequences) == list(range(1, len(sequences) + 1)), key
    # no cycle
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        state[node] = 1
        for prereq in by_id[node]["prereqs"]:
            assert state.get(prereq) != 1, f"prereq cycle through {prereq}"
            if prereq not in state:
                visit(prereq)
        state[node] = 2

    for seed in seeds:
        if seed["id"] not in state:
            visit(seed["id"])


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_an_r5_lesson_is_an_alias_of_one_point_only(lang: str) -> None:
    owners: dict[str, str] = {}
    for point_id, aliases in aliases_for(load_seeds(lang)).items():
        for alias in aliases:
            assert alias not in owners, f"{alias} is an alias of both {owners[alias]} and {point_id}"
            owners[alias] = point_id
    assert owners  # something is actually converted


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_points_already_on_disk_agree_with_their_seed(lang: str) -> None:
    seeds = {s["id"]: s for s in load_seeds(lang)}
    for point_id, point in load_points(lang).items():
        if point_id in NOT_SEEDED:
            continue
        assert point_id in seeds, f"{point_id} is on disk but has no seed"
        assert point["function"] == seeds[point_id]["function"], point_id
        if point_id not in RELEVELED:
            assert point["level"]["value"] == str(seeds[point_id]["level"]), point_id


def test_semantic_seed_audit_reports_unclassified_and_placeholder_titles(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "zh")
    lab.write()
    inventory = lab.root / "inventory"
    inventory.mkdir(parents=True, exist_ok=True)
    seeds = [
        {"id": "zh.good", "level": "1", "function": "fn.alpha", "point_type": "other", "native_title": "把字句", "title": {"vi": "Câu chữ 把", "en": "Ba construction"}, "r5": [], "error_tags": ["other"], "contrasts": [], "prereqs": [], "sequence": 1, "anchors": []},
        {"id": "zh.bad", "level": "1", "function": "fn.catalog_unclassified", "point_type": "other", "native_title": "ba_suggestion", "title": {"vi": "x", "en": "x"}, "r5": [], "error_tags": ["other"], "contrasts": [], "prereqs": [], "sequence": 2, "anchors": []},
        {"id": "zh.mixed", "level": "1", "function": "fn.alpha", "point_type": "other", "native_title": "把 với bổ ngữ", "title": {"vi": "x", "en": "x"}, "r5": [], "error_tags": ["other"], "contrasts": [], "prereqs": [], "sequence": 3, "anchors": []},
    ]
    (inventory / "seeds_zh.yaml").write_text(yaml.safe_dump(seeds, allow_unicode=True, sort_keys=False), encoding="utf-8")
    findings = audit_seed_semantics("zh", lab.root)
    by_id = {}
    for finding in findings:
        by_id.setdefault(finding["id"], set()).add(finding["code"])
    assert "zh.good" not in by_id
    assert {"function.unclassified", "native_title.placeholder", "native_title.non_zh"} <= by_id["zh.bad"]
    assert "native_title.mixed_language" in by_id["zh.mixed"]


def test_a_seed_carries_the_r5_sources_and_anchors_into_the_point() -> None:
    point = apply_seed(None, "en", "en.modals.must_have_to")
    assert point is not None
    assert point["source_refs"] == {"r5": ["a2-must-have-to", "b1-obligation-must-have-to-need-to"]}
    assert point["aliases"] == ["a2-must-have-to", "b1-obligation-must-have-to-need-to"]
    assert point["source_anchors"]["status"] == "anchored" and point["level"] == {"framework": "cefr", "value": "A2", "rank": 2}
    piece = apply_seed(None, "en", "en.possessive_s")  # the third piece of a split: R5 source yes, alias no
    assert piece["source_refs"]["r5"] == ["a1-possessive-adjectives-pronouns-and-possessive-s"] and piece["aliases"] == []
    assert apply_seed(None, "zh", "zh.svo_basic")["source_anchors"] == {"status": "unanchored", "items": []}


def test_a_seed_only_touches_metadata_of_an_existing_point() -> None:
    existing = load_points("en")["en.there_is_are"]
    seeded = apply_seed(existing, "en", "en.there_is_are")
    assert seeded["examples"] == existing["examples"] and seeded["common_mistakes"] == existing["common_mistakes"]
    assert apply_seed(None, "en", "en.not_a_seed") is None


def test_generate_starts_a_new_point_from_its_seed_and_realizes_it(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    root = lab.root
    (root / "inventory").mkdir(exist_ok=True)
    seeds = [{
        "id": "en.gamma", "level": "A1", "function": "fn.alpha", "point_type": "morphology", "native_title": "Gamma",
        "title": {"vi": "Gamma", "en": "Gamma"}, "r5": [], "error_tags": ["agreement"], "contrasts": [], "prereqs": [],
        "sequence": 2, "anchors": [], "batch": "core",
    }]
    (root / "inventory" / "seeds_en.yaml").write_text(yaml.safe_dump(seeds), encoding="utf-8")
    functions = yaml.safe_load((root / "functions" / "functions.yaml").read_text(encoding="utf-8"))
    functions["functions"][0].setdefault("planned", {})["en"] = ["en.gamma"]
    (root / "functions" / "functions.yaml").write_text(yaml.safe_dump(functions), encoding="utf-8")
    manifest = read_json(root / "content" / "en" / "_set.json")
    assert manifest["explanation_locales"] == ["vi"]

    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=root / ".cache",
                     transport=v04_transport({**CANNED_V04, "compare": []}))
    outcome = Generator(lang="en", l1="vi", llm=llm, root=root).generate("en.gamma")
    assert outcome.status == "written", outcome.reason
    written = read_json(root / "content" / "en" / "en.gamma.json")
    assert written["header"]["native_title"] == "Gamma" and written["sequence"] == 2 and written["status"] == "draft_ai"
    realized = yaml.safe_load((root / "functions" / "functions.yaml").read_text(encoding="utf-8"))["functions"][0]
    assert "en.gamma" in realized["realizations"]["en"] and "en.gamma" not in realized["planned"]["en"]
    assert validate_lang("en", root).ok, validate_lang("en", root).issues


def test_register_realization_is_idempotent(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    point = lab.points["en.alpha"]
    assert register_realization(point, lab.root) is False  # already realized
