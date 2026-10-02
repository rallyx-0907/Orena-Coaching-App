"""Hardening: Codex handoff shape of the UI fixtures, GF0025 reciprocal proof, fail-closed generation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import httpx
import pytest
import yaml
from jsonschema import Draft202012Validator

from grammar_lab.pipeline.canonical import canonical_dir, catalog_path, write_catalog, zh_source_coverage
from grammar_lab.pipeline.generate import Generator
from grammar_lab.pipeline.jsonio import format_json, read_json
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.pipeline.seed import GenerationBlocked, check_generation_gate, load_catalog, load_seeds, select_ids
from grammar_lab.pipeline.ui_fixtures import (
    CODEX_REQUIRED_LOCALES, DEMO_POINTS, FIXTURE_DIR, INDEX_NAME, from_codex_export, locale_gaps, to_codex_export,
)
from grammar_lab.pipeline.validate import GRAMMAR_SCHEMA_PATH, LAB_ROOT, validate_lang
from grammar_lab.tests.conftest import Lab

# --- fixtures in the shape codex/work reads ------------------------------------------------------------


def _fixture(lang: str) -> dict:
    return read_json(LAB_ROOT / FIXTURE_DIR / f"{DEMO_POINTS[lang]}.json")


def _placeholders(lang: str) -> list[str]:
    entries = read_json(LAB_ROOT / FIXTURE_DIR / INDEX_NAME)["fixtures"]
    return next(e for e in entries if e["lang"] == lang)["en_placeholder_paths"]


@pytest.mark.parametrize("lang,level,codex_target,lab_target", [("en", "A1", "en", "en"), ("zh", "1", "zh", "zh-Hans")])
def test_demo_fixture_is_codex_shaped_and_its_lab_form_validates_against_the_schema(
    lang: str, level: str, codex_target: str, lab_target: str
) -> None:
    export = _fixture(lang)
    assert export["target_lang"] == codex_target  # the shape codex/work reads: en | zh, never zh-Hans
    assert '"zh-Hans"' not in json.dumps(export, ensure_ascii=False)
    point = from_codex_export(export, _placeholders(lang))  # the normalisation is reversible...
    assert point["target_lang"] == lab_target
    schema = read_json(LAB_ROOT / GRAMMAR_SCHEMA_PATH)  # ...and what comes back is a valid Grammar Lab point
    errors = sorted(Draft202012Validator(schema).iter_errors(point), key=lambda e: list(e.path))
    assert errors == [], [f"{list(e.path)}: {e.message}" for e in errors]
    assert point["id"] == DEMO_POINTS[lang] and point["level"]["value"] == level
    assert point["schema_version"] == "0.4" and point["point_type"] == "tense_aspect"
    catalog = {record["id"]: record for record in load_catalog(lang)}
    assert point["id"] in catalog and catalog[point["id"]]["level"] == level
    assert to_codex_export(point)[0] == export  # round trip is exact


def test_normalisation_renames_zh_hans_and_declares_en_placeholders_without_inventing_text() -> None:
    internal = {
        "target_lang": "zh-Hans",
        "header": {"title": {"vi": "a", "zh-Hans": "甲"}, "summary": {"vi": "s", "en": "S"}},
    }
    out, placeholders = to_codex_export(internal)
    assert out["target_lang"] == "zh" and out["header"]["title"] == {"vi": "a", "zh": "甲", "en": "a"}
    assert out["header"]["summary"] == {"vi": "s", "en": "S"}  # an existing en is never touched
    assert placeholders == ["header.title"]  # exactly the map whose en is a copy of vi
    assert from_codex_export(out, placeholders) == internal
    with pytest.raises(KeyError):
        to_codex_export({**internal, "target_lang": "ja"})  # an unmapped language is a loud failure


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_every_locale_map_of_the_export_carries_the_locales_codex_requires(lang: str) -> None:
    export = _fixture(lang)
    assert CODEX_REQUIRED_LOCALES == ("vi", "en")
    assert locale_gaps(export) == []
    # Drift guard: placeholder metadata must exactly describe gaps restored in the Grammar Lab form.
    # An empty list is valid once the real source content has genuine English in every locale map.
    placeholders = _placeholders(lang)
    internal = from_codex_export(export, placeholders)
    assert sorted(locale_gaps(internal)) == sorted(placeholders)


def test_reference_fixtures_stay_draft_ai_and_are_not_a_production_feed() -> None:
    index = read_json(LAB_ROOT / FIXTURE_DIR / INDEX_NAME)
    assert index["learner_production_feed"] is False and "never a learner production feed" in index["feed"]
    for entry in index["fixtures"]:
        point = read_json(LAB_ROOT / FIXTURE_DIR / entry["file"])
        assert point["status"] == entry["status"] == "draft_ai" and point["review"] is None
        assert entry["production_ready"] is False  # draft_ai alone is sufficient to keep this out of production
        assert isinstance(entry["en_placeholder_paths"], list)
        source = read_json(LAB_ROOT / entry["content_source"])
        assert source["status"] == "draft_ai"  # source not promoted either
        # The index describes current source gaps truthfully; it need not stay non-empty forever.
        assert sorted(entry["en_placeholder_paths"]) == sorted(locale_gaps(source))


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_demo_fixture_passes_every_deterministic_check(lang: str, tmp_path: Path) -> None:
    """validate_lang over the shipped content plus the fixture (in Grammar Lab's own form). The only findings
    allowed are references to catalogue points that are not written yet (prereqs/contrasts)."""
    for name in ("schema", "functions", "cast"):
        shutil.copytree(LAB_ROOT / name, tmp_path / name)
    shutil.copytree(LAB_ROOT / "content" / lang, tmp_path / "content" / lang)
    lab_form = from_codex_export(_fixture(lang), _placeholders(lang))
    (tmp_path / "content" / lang / f"{DEMO_POINTS[lang]}.json").write_text(format_json(lab_form), encoding="utf-8")
    report = validate_lang(lang, tmp_path)
    catalog_ids = {record["id"] for record in load_catalog(lang)}
    mine = [issue for issue in report.issues if issue.file.endswith(f"{DEMO_POINTS[lang]}.json")]
    assert {issue.code for issue in mine} <= {"ref.unknown_prereq", "ref.unknown_contrast"}, mine
    for issue in mine:
        assert issue.message.rsplit(" ", 1)[-1] in catalog_ids, issue


# --- GF0025 reciprocal proof ---------------------------------------------------------------------------


def _gf_root(tmp_path: Path, source_map: dict[str, list[str]], points: dict[str, list[str]]) -> Path:
    directory = canonical_dir(tmp_path)
    directory.mkdir(parents=True)
    (directory / "zh_gf0025_source.yaml").write_text(
        yaml.safe_dump({"items": [{"source_id": sid} for sid in ("S1", "S2")]}), encoding="utf-8")
    (directory / "zh_source_map.yaml").write_text(
        yaml.safe_dump({"items": [{"source_id": sid, "maps_to": to} for sid, to in source_map.items()]}), encoding="utf-8")
    (directory / "zh.yaml").write_text(
        yaml.safe_dump({"items": [{"id": pid, "source_items": src} for pid, src in points.items()]}), encoding="utf-8")
    return tmp_path


def test_gf0025_proof_passes_when_map_and_catalog_agree_exactly(tmp_path: Path) -> None:
    root = _gf_root(tmp_path, {"S1": ["zh.a"], "S2": ["zh.a", "zh.b"]}, {"zh.a": ["S1", "S2"], "zh.b": ["S2"]})
    assert zh_source_coverage(root)["covered"] == 2


def test_gf0025_proof_fails_when_the_catalog_claims_more_points_than_the_map(tmp_path: Path) -> None:
    # map says S1 -> {A}; the canonical rows put S1 on {A, B}: a subset relation would have passed this
    root = _gf_root(tmp_path, {"S1": ["zh.a"], "S2": ["zh.b"]}, {"zh.a": ["S1"], "zh.b": ["S1", "S2"]})
    report = zh_source_coverage(root)
    assert report["covered"] == 1 and report["missing"] == ["S1"] and report["reciprocal_mismatches"] == ["S1"]


def test_gf0025_proof_fails_when_the_map_names_more_points_than_the_catalog(tmp_path: Path) -> None:
    root = _gf_root(tmp_path, {"S1": ["zh.a", "zh.b"], "S2": ["zh.b"]}, {"zh.a": ["S1"], "zh.b": ["S2"]})
    assert zh_source_coverage(root)["missing"] == ["S1"]


def test_gf0025_proof_flags_a_point_citing_a_row_the_map_never_mentions(tmp_path: Path) -> None:
    root = _gf_root(tmp_path, {"S1": ["zh.a"]}, {"zh.a": ["S1", "S2"]})
    report = zh_source_coverage(root)
    assert report["missing"] == ["S2"] and report["orphan_citations"] == ["S2"]


# --- generation gate: fail closed before a provider is touched -----------------------------------------


def _gated_root(tmp_path: Path) -> Path:
    """A tiny lab with a canonical catalogue of three points: two reviewed seeds and one default_safe."""
    lab = Lab(tmp_path, "en")
    lab.write()
    directory = canonical_dir(tmp_path)
    directory.mkdir(parents=True)
    items = [
        {"id": pid, "level": level, "title": pid, "conversion": "keep", "r5_sources": [], "r5_aliases": []}
        for pid, level in (("en.alpha", "A1"), ("en.beta", "A2"), ("en.delta", "A2"))
    ]
    (directory / "en.yaml").write_text(yaml.safe_dump({"items": items}), encoding="utf-8")
    seeds = [
        {"id": pid, "level": level, "function": "fn.alpha", "point_type": "other", "native_title": pid,
         "title": {"vi": pid}, "r5": [], "error_tags": ["agreement"], "contrasts": [], "prereqs": [], "sequence": n,
         "anchors": [], "batch": "core"}
        for n, (pid, level) in enumerate((("en.alpha", "A1"), ("en.beta", "A2")), start=1)
    ]
    (tmp_path / "inventory").mkdir(exist_ok=True)
    (tmp_path / "inventory" / "seeds_en.yaml").write_text(yaml.safe_dump(seeds), encoding="utf-8")
    write_catalog("en", tmp_path)
    return tmp_path


def _stale(root: Path) -> None:
    path = catalog_path("en", root)
    path.write_text(path.read_text(encoding="utf-8") + "# drift\n", encoding="utf-8")


def test_gate_passes_reviewed_points_on_a_current_catalog(tmp_path: Path) -> None:
    check_generation_gate("en", ["en.alpha", "en.beta"], _gated_root(tmp_path))


def test_gate_blocks_default_safe_points_unless_explicitly_overridden(tmp_path: Path) -> None:
    root = _gated_root(tmp_path)
    with pytest.raises(GenerationBlocked, match="default_safe"):
        check_generation_gate("en", ["en.alpha", "en.delta"], root)  # one unreviewed point blocks the batch
    check_generation_gate("en", ["en.alpha", "en.delta"], root, allow_default_safe=True)


def test_gate_blocks_a_stale_or_missing_catalog_even_with_the_override(tmp_path: Path) -> None:
    root = _gated_root(tmp_path)
    path = canonical_dir(root) / "en.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["items"][0]["level"] = "B1"  # canonical moved; catalog_en.yaml was not regenerated
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(GenerationBlocked, match="stale"):
        check_generation_gate("en", ["en.alpha"], root, allow_default_safe=True)
    write_catalog("en", root)
    check_generation_gate("en", ["en.alpha"], root)
    catalog_path("en", root).unlink()
    with pytest.raises(GenerationBlocked, match="missing or stale"):
        check_generation_gate("en", ["en.alpha"], root)


def test_generator_makes_no_provider_call_on_a_stale_or_default_safe_catalog(tmp_path: Path) -> None:
    root = _gated_root(tmp_path)
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500, json={"error": "a provider must not be reached"})

    llm = LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=root / ".cache",
                    transport=httpx.MockTransport(handler))
    generator = Generator(lang="en", l1="vi", llm=llm, root=root)
    with pytest.raises(GenerationBlocked, match="default_safe"):
        generator.generate("en.delta")
    _stale(root)
    with pytest.raises(GenerationBlocked, match="stale"):
        generator.generate("en.alpha")
    assert calls == []


def test_cli_generate_is_blocked_before_the_provider_lock_and_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from typer.testing import CliRunner

    from grammar_lab.pipeline import cli as cli_module

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("the gate must run before the lock and the client exist")

    monkeypatch.setattr(cli_module.live_lock, "hold", forbidden)
    monkeypatch.setattr(cli_module, "LLMClient", forbidden)
    root = _gated_root(tmp_path)
    runner = CliRunner()
    blocked = runner.invoke(cli_module.app, ["generate", "--lang", "en", "--level", "A2", "--root", str(root)])
    assert blocked.exit_code == 2 and "default_safe" in blocked.output
    _stale(root)
    stale = runner.invoke(cli_module.app, ["generate", "--lang", "en", "--level", "A1", "--root", str(root)])
    assert stale.exit_code == 2 and "stale" in stale.output
    # the override is a flag of its own and still cannot pass a stale catalogue
    override = runner.invoke(cli_module.app, [
        "generate", "--lang", "en", "--level", "A2", "--root", str(root), "--allow-default-safe-metadata",
    ])
    assert override.exit_code == 2 and "stale" in override.output


def test_the_real_catalog_has_full_reviewed_metadata_and_passes_generation_gate() -> None:
    for lang in ("en", "zh"):
        records = load_catalog(lang)
        seeded = {seed["id"] for seed in load_seeds(lang)}
        assert len(records) == len(seeded)
        assert {record["id"] for record in records} == seeded
        assert all(record["catalog"]["metadata_origin"] == "reviewed_seed" for record in records)
        check_generation_gate(lang, [record["id"] for record in records])
