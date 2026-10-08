"""Grammar export package v1: profile, canonical hash, R5 map, fail-closed export, zero provider calls."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import shutil
import socket
import unicodedata
from pathlib import Path
from typing import Any

import pytest
import yaml

from grammar_lab.pipeline import export_package as export_module
from grammar_lab.pipeline.canonical import write_catalog
from grammar_lab.pipeline.export_package import ExportError, export_package, package_to_zip, validate_package
from grammar_lab.pipeline.export_profile import (
    APP_LOCALES, APP_REQUIRED_LOCALES, APP_TARGET_LANG, BODY_DROPPED, PROFILE_ID, PROFILE_SCHEMA_PATH, CanonicalJSONError,
    canonical_json, content_hash, derive_profile_schema, from_app_point, iter_locale_maps, load_internal_schema,
    load_profile_schema, locale_problems, profile_drift, to_app_point,
)
from grammar_lab.pipeline.jsonio import read_json, write_json
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.pipeline.r5_map import build_r5_map, load_dropped_r5_ids, validate_r5_map
from grammar_lab.pipeline.seed import load_catalog
from grammar_lab.pipeline.validate import GRAMMAR_SCHEMA_PATH, LAB_ROOT

GOLDEN = LAB_ROOT / "fixtures" / "export" / "golden_vector.json"
GOLDEN_SHA256 = "cf92888909aadba47cac25209a173fdf1fa9ee0f66dacd7e425b2326be19ee27"
TEMPLATES = {"en": "en.present_continuous.now", "zh": "zh.le_completion"}
REVIEW = {"reviewer": "tester", "reviewed_at": "2026-09-30T00:00:00Z", "seconds": 60, "note": None}


# --- a throwaway lab with approved, bilingual points ---------------------------------------------------


def _bilingual(point: dict[str, Any]) -> dict[str, Any]:
    """Test data only: give every locale map a real-looking, different ``en`` (never done by production code)."""
    for _, mapping in iter_locale_maps(point):
        mapping.setdefault("en", f"[en] {len(mapping['vi'])} chars")
    return point


# id -> (R5 sources, R5 aliases it is primary of, contrasts). r3 is split: beta primary, gamma secondary.
SHAPE = {
    "alpha": (["r1", "r2"], ["r1", "r2"], ["beta"]),
    "beta": (["r3"], ["r3"], ["alpha", "gamma"]),
    "gamma": (["r3", "r4"], ["r4"], ["beta"]),
}


def build_lab(tmp: Path, lang: str = "en", status: str = "approved") -> Path:
    root = tmp / f"lab_{lang}"
    for name in ("schema", "cast"):
        shutil.copytree(LAB_ROOT / name, root / name)
    template = read_json(LAB_ROOT / "content" / lang / f"{TEMPLATES[lang]}.json")
    level = template["level"]["value"]
    ids = {key: f"{lang}.{key}" for key in SHAPE}
    target = template["target_lang"]
    functions = {"schema_version": "0.2", "functions": [{
        "id": "fn.test", "title": {"vi": "Chức năng thử", "en": "Test function", "zh-Hans": "测试功能"},
        "realizations": {target: sorted(ids.values())},
    }]}
    (root / "functions").mkdir()
    (root / "functions" / "functions.yaml").write_text(yaml.safe_dump(functions, allow_unicode=True), encoding="utf-8")
    shutil.copy(LAB_ROOT / "content" / lang / "_set.json", (root / "content" / lang).mkdir(parents=True) or root / "content" / lang / "_set.json")
    seeds, items = [], []
    for n, (key, (sources, aliases, contrasts)) in enumerate(SHAPE.items(), start=1):
        pid = ids[key]
        point = copy.deepcopy(template)
        point.update(id=pid, function="fn.test", prereqs=[], contrasts=[ids[c] for c in contrasts], sequence=n,
                     status=status, review=dict(REVIEW), flags=[])
        point["compare"] = [{**template["compare"][0], "with": ids[c]} for c in contrasts]
        point["provenance"] = {"model": "test-model", "prompt_version": "v1", "run_id": "run1", "generated_at": "2026-09-29T00:00:00Z"}
        write_json(root / "content" / lang / f"{pid}.json", _bilingual(point))
        seeds.append({
            "id": pid, "level": level, "function": "fn.test", "point_type": template["point_type"],
            "native_title": template["header"]["native_title"], "title": {"vi": f"Thử {n}", "en": f"Test {n}"},
            "r5": sources, "error_tags": template["error_tags"], "contrasts": [ids[c] for c in contrasts], "prereqs": [],
            "sequence": n, "anchors": [], "batch": "core",
        })
        items.append({"id": pid, "level": level if lang == "en" else f"HSK{level}", "title": pid, "conversion": "keep",
                      "r5_sources": sources, "r5_aliases": aliases})
    (root / "inventory" / "canonical_v1").mkdir(parents=True)
    (root / "inventory" / "canonical_v1" / f"{lang}.yaml").write_text(yaml.safe_dump({"items": items}), encoding="utf-8")
    (root / "inventory" / f"seeds_{lang}.yaml").write_text(yaml.safe_dump(seeds, allow_unicode=True), encoding="utf-8")
    write_catalog(lang, root)
    shutil.copy(LAB_ROOT / PROFILE_SCHEMA_PATH, root / PROFILE_SCHEMA_PATH)
    return root


def do_export(root: Path, lang: str = "en", out: str = "out", ids: list[str] | None = None, **kw: Any) -> Any:
    return export_package(
        lang, ids or [f"{lang}.{key}" for key in SHAPE], root, root / out, set_version="test.1",
        source_commit="0" * 40, exported_at="2026-09-30T12:00:00Z", **kw,
    )


def _edit(root: Path, lang: str, key: str, change: Any) -> None:
    path = root / "content" / lang / f"{lang}.{key}.json"
    point = read_json(path)
    change(point)
    write_json(path, point)


@pytest.fixture
def en_lab(tmp_path: Path) -> Path:
    return build_lab(tmp_path, "en")


# --- export profile ------------------------------------------------------------------------------------


def test_committed_profile_schema_is_exactly_what_the_internal_schema_derives_to() -> None:
    assert profile_drift() is None
    assert load_profile_schema() == derive_profile_schema(load_internal_schema())


def test_profile_boundary_constants_and_closed_body() -> None:
    schema = load_profile_schema()
    defs = schema["$defs"]
    assert defs["target_lang"]["enum"] == ["en", "zh"] == list(APP_TARGET_LANG.values())
    assert defs["locale"]["enum"] == list(APP_LOCALES) == ["vi", "en", "zh"]
    assert defs["locale_map"]["required"] == list(APP_REQUIRED_LOCALES) == ["vi", "en"]
    point = defs["grammar_point"]
    assert point["additionalProperties"] is False and point["properties"]["status"] == {"const": "approved"}
    for name in BODY_DROPPED:
        assert name not in point["properties"] and name not in point["required"], name
    assert {"sequence", "aliases", "header", "quick_practice"} <= set(point["required"])
    assert "zh-Hans" not in json.dumps(schema) and "ja" not in defs["target_lang"]["enum"]
    internal = load_internal_schema()  # the internal schema stays multi-version and keeps zh-Hans
    assert "zh-Hans" in internal["$defs"]["target_lang"]["enum"] and "0.2" in internal["$defs"]["schema_version"]["enum"]


def test_upstream_contract_drift_makes_export_refuse(en_lab: Path) -> None:
    schema_path = en_lab / GRAMMAR_SCHEMA_PATH
    schema = read_json(schema_path)
    schema["$defs"]["point_type"]["enum"].append("discourse")  # the internal contract moved
    write_json(schema_path, schema)
    assert profile_drift(en_lab) is not None
    with pytest.raises(ExportError) as caught:
        do_export(en_lab)
    assert any(p.startswith("profile.drift") for p in caught.value.problems)
    assert not (en_lab / "out").exists()
    (en_lab / PROFILE_SCHEMA_PATH).unlink()
    assert "missing" in (profile_drift(en_lab) or "")


def test_zh_hans_internal_to_zh_app_round_trip() -> None:
    internal = read_json(LAB_ROOT / "content" / "zh" / "zh.le_completion.json")
    assert internal["target_lang"] == "zh-Hans"
    internal["header"]["title"]["zh-Hans"] = "动态助词“了”"  # the internal locale key for Chinese
    internal["header"]["summary"]["zh-Hans"] = "了 表示完成。"
    body = to_app_point(internal)
    assert body["target_lang"] == "zh" and "zh-Hans" not in json.dumps(body, ensure_ascii=False)
    assert body["header"]["title"]["zh"] == "动态助词“了”" and body["header"]["summary"]["zh"] == "了 表示完成。"
    assert not set(BODY_DROPPED) & set(body)  # provenance/review/flags/source_anchors/schema_version never leak
    restored = from_app_point(body)
    assert restored["target_lang"] == "zh-Hans"
    assert restored == {k: v for k, v in internal.items() if k not in BODY_DROPPED}
    assert internal["target_lang"] == "zh-Hans" and "zh" not in internal["header"]["title"]  # input untouched
    with pytest.raises(KeyError):
        to_app_point({**internal, "target_lang": "ja"})


def test_to_app_point_never_adds_text() -> None:
    internal = read_json(LAB_ROOT / "content" / "en" / "en.present_continuous.now.json")
    # Contract test, not a fixture-state test: force one missing locale even after the real content is fully bilingual.
    missing_path, missing_map = next((path, mapping) for path, mapping in iter_locale_maps(internal) if "vi" in mapping)
    missing_map.pop("en", None)
    before = copy.deepcopy(internal)

    body = to_app_point(internal)
    body_maps = dict(iter_locale_maps(body))
    assert "en" not in body_maps[missing_path]  # the gap is reported, never filled by the production transform
    assert any(problem == f"{missing_path}: locale.missing en" for problem in locale_problems(body))
    assert internal == before  # conversion is non-mutating


# --- canonical JSON and the golden vector ------------------------------------------------------------


def test_canonical_hash_golden_vector() -> None:
    vector = read_json(GOLDEN)
    assert vector["sha256"] == GOLDEN_SHA256 == content_hash(vector["value"])
    assert canonical_json(vector["value"]).decode("utf-8") == vector["canonical_json"]
    assert hashlib.sha256(vector["canonical_json"].encode("utf-8")).hexdigest() == GOLDEN_SHA256  # the hashed text itself
    text = vector["canonical_json"]
    assert " " not in text.replace("Trợ từ 了 (hoàn thành): hành động đã xong", "").replace(
        "The particle 了: completed action", "").replace("Hôm qua tôi đã mua một cuốn sách.", "").replace(
        "I bought a book yesterday.", "")  # no whitespace between tokens
    assert "\\u" not in text and "Trợ" in text and "动态助词" in text and "dòng" in text  # no ASCII escaping
    assert text.startswith('{"examples":[{"form":') and text.index('"header"') < text.index('"id"')  # keys sorted


def test_design_doc_states_the_golden_hash_and_the_profile_constants() -> None:
    doc = (LAB_ROOT.parent / "docs" / "grammar_lab" / "INTEGRATION_DESIGN.md").read_text(encoding="utf-8")
    assert GOLDEN_SHA256 in doc and PROFILE_ID in doc and "golden_vector.json" in doc
    assert "D-105" in doc and "GRAMMAR_CONTENT_STORE" in doc


def test_canonical_form_is_independent_of_key_order_and_whitespace() -> None:
    value = read_json(GOLDEN)["value"]
    shuffled = json.loads(json.dumps(value, ensure_ascii=True, indent=3, sort_keys=False)[::1])
    reordered = {key: shuffled[key] for key in reversed(list(shuffled))}
    assert content_hash(reordered) == content_hash(value) == GOLDEN_SHA256


def test_canonical_form_has_no_unicode_normalisation_and_rejects_floats() -> None:
    nfc, nfd = unicodedata.normalize("NFC", "ộ"), unicodedata.normalize("NFD", "ộ")
    assert nfc != nfd and content_hash({"a": nfc}) != content_hash({"a": nfd})
    for bad in ({"a": 1.0}, {"a": [0.5]}, {"a": float("nan")}):
        with pytest.raises(CanonicalJSONError):
            content_hash(bad)
    assert content_hash({"a": 1}) != content_hash({"a": True})


# --- R5 map --------------------------------------------------------------------------------------------


def _bodies(aliases: dict[str, list[str]], splits: dict[str, list[str]] | None = None) -> dict[str, dict[str, Any]]:
    return {pid: {"aliases": a, "source_refs": ({"r5_split": splits[pid]} if splits and pid in splits else {})}
            for pid, a in aliases.items()}


def _records() -> list[dict[str, Any]]:
    return [{"id": f"en.{key}", "r5": sources, "aliases": aliases} for key, (sources, aliases, _) in SHAPE.items()]


def test_r5_map_dispositions_replaced_merged_split_and_dropped() -> None:
    rows, problems = build_r5_map(_records(), ["en.alpha", "en.beta", "en.gamma"], ["r9"])
    assert problems == []
    by = {(r["r5_id"], r["point_id"]): r for r in rows}
    assert by[("r1", "en.alpha")]["disposition"] == by[("r2", "en.alpha")]["disposition"] == "merged"  # two R5 ids -> one point
    assert by[("r4", "en.gamma")]["disposition"] == "replaced" and by[("r4", "en.gamma")]["is_primary"]
    assert by[("r3", "en.beta")] == {"r5_id": "r3", "point_id": "en.beta", "is_primary": True, "disposition": "split_primary"}
    assert by[("r3", "en.gamma")] == {"r5_id": "r3", "point_id": "en.gamma", "is_primary": False, "disposition": "split_secondary"}
    assert by[("r9", None)] == {"r5_id": "r9", "point_id": None, "is_primary": False, "disposition": "dropped"}
    bodies = _bodies({"en.alpha": ["r1", "r2"], "en.beta": ["r3"], "en.gamma": ["r4"]}, {"en.gamma": ["r3"]})
    assert validate_r5_map(rows, bodies) == []
    assert rows == sorted(rows, key=lambda r: (r["r5_id"], not r["is_primary"], r["point_id"] or ""))  # deterministic order


def test_r5_map_refuses_a_duplicate_primary() -> None:
    records = _records()
    records[2]["aliases"] = ["r3", "r4"]  # gamma claims r3 as an alias too: two primaries
    rows, problems = build_r5_map(records, ["en.alpha", "en.beta", "en.gamma"])
    assert any("r3 is an alias of 2 points" in p for p in problems)
    bodies = _bodies({"en.alpha": ["r1", "r2"], "en.beta": ["r3"], "en.gamma": ["r3", "r4"]})
    assert any(p.startswith("aliases.duplicate") for p in validate_r5_map(rows, bodies))
    two_primaries = [
        {"r5_id": "r3", "point_id": "en.beta", "is_primary": True, "disposition": "split_primary"},
        {"r5_id": "r3", "point_id": "en.gamma", "is_primary": True, "disposition": "split_primary"},
    ]
    assert any("2 primary rows" in p for p in validate_r5_map(two_primaries, bodies))


def test_r5_map_alias_sits_on_the_primary_only_and_secondaries_record_provenance() -> None:
    rows, _ = build_r5_map(_records(), ["en.alpha", "en.beta", "en.gamma"])
    aliased_secondary = _bodies({"en.alpha": ["r1", "r2"], "en.beta": ["r3"], "en.gamma": ["r3", "r4"]}, {"en.gamma": ["r3"]})
    assert any("also an alias of secondary en.gamma" in p for p in validate_r5_map(rows, aliased_secondary))
    no_provenance = _bodies({"en.alpha": ["r1", "r2"], "en.beta": ["r3"], "en.gamma": ["r4"]})
    assert any("does not record r3 in source_refs.r5_split" in p for p in validate_r5_map(rows, no_provenance))
    primary_without_alias = _bodies({"en.alpha": ["r1", "r2"], "en.beta": [], "en.gamma": ["r4"]}, {"en.gamma": ["r3"]})
    assert any("primary point en.beta does not list r3" in p for p in validate_r5_map(rows, primary_without_alias))


@pytest.mark.parametrize("rows,needle", [
    ([{"r5_id": "r1", "point_id": None, "is_primary": False, "disposition": "replaced"}], "null exactly when"),
    ([{"r5_id": "r1", "point_id": "en.alpha", "is_primary": True, "disposition": "dropped"}], "null exactly when"),
    ([{"r5_id": "r1", "point_id": "en.zzz", "is_primary": True, "disposition": "replaced"}], "not in the package"),
    ([{"r5_id": "r1", "point_id": "en.alpha", "is_primary": True, "disposition": "teleported"}], "unknown disposition"),
    ([{"r5_id": "r1", "point_id": "en.alpha"}], "keys must be exactly"),
    ([{"r5_id": "r1", "point_id": "en.alpha", "is_primary": True, "disposition": "replaced"},
      {"r5_id": "r1", "point_id": None, "is_primary": False, "disposition": "dropped"}], "dropped and also mapped"),
    ([{"r5_id": "r1", "point_id": "en.alpha", "is_primary": True, "disposition": "split_primary"}], "without a secondary"),
    ([], "alias of en.alpha but has no r5_map row"),  # never inferred from aliases
])
def test_r5_map_invalid_rows_are_refused(rows: list[dict[str, Any]], needle: str) -> None:
    bodies = _bodies({"en.alpha": ["r1"]})
    assert any(needle in p for p in validate_r5_map(rows, bodies)), validate_r5_map(rows, bodies)


def test_r5_map_refuses_half_a_split_and_dropped_ids_that_are_mapped() -> None:
    _, problems = build_r5_map(_records(), ["en.beta"])  # gamma holds the other piece of r3
    assert any("r3 also has pieces outside this package (en.gamma)" in p for p in problems)
    _, problems = build_r5_map(_records(), ["en.alpha"], ["r1"])
    assert any("r1 is dropped and also has a replacement" in p for p in problems)


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_the_whole_real_catalog_obeys_the_primary_alias_rule(lang: str) -> None:
    records = load_catalog(lang)
    ids = [record["id"] for record in records]
    dropped = load_dropped_r5_ids(lang, LAB_ROOT.parent / "docs" / "grammar_lab" / "r5_conversion_map.tsv")
    rows, problems = build_r5_map(records, ids, dropped)
    assert problems == [] and dropped
    bodies = {}
    for record in records:
        aliases = record["aliases"]
        bodies[record["id"]] = {"aliases": aliases, "source_refs": {"r5_split": [r for r in record["r5"] if r not in aliases]}}
    assert validate_r5_map(rows, bodies) == []
    kinds = {row["disposition"] for row in rows}
    assert kinds == {"replaced", "merged", "split_primary", "split_secondary", "dropped"}
    assert len({row["r5_id"] for row in rows if row["is_primary"] or row["disposition"] == "dropped"}) == len(
        {row["r5_id"] for row in rows})  # one primary (or drop) per R5 id


# --- the export ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_export_builds_a_valid_approved_package(tmp_path: Path, lang: str) -> None:
    root = build_lab(tmp_path, lang)
    result = do_export(root, lang, dropped=["r9"])
    out = result.out_dir
    assert validate_package(out, root) == []
    manifest = read_json(out / "package.json")
    assert manifest["export_profile"] == PROFILE_ID and manifest["language"] == lang
    assert manifest["validator"] == {"tool": "grammar_lab.export_package", "version": "1", "passed": True, "codes": []}
    assert manifest["package_hash"] == result.package_hash and manifest["source_commit"] == "0" * 40
    assert manifest["rights"]["external_text_included"] is False and manifest["rights"]["attestation_required_at_import"]
    assert sorted(p.name for p in (out / "points").iterdir()) == sorted(f"{lang}.{k}.json" for k in SHAPE)
    target = "en" if lang == "en" else "zh"
    for entry in manifest["points"]:
        body = read_json(out / "points" / f"{entry['id']}.json")
        assert body["status"] == "approved" and body["target_lang"] == target
        assert not set(BODY_DROPPED) & set(body)  # no provenance/review/flags/anchors/schema_version in a body
        assert entry["content_hash"] == content_hash(body)
        assert entry["provenance"]["reviewer"] == "tester" and entry["provenance"]["run_id"] == "run1"
        assert locale_problems(body) == []
    by_row = {(r["r5_id"], r["point_id"]): r["disposition"] for r in manifest["r5_map"]}
    assert by_row[("r3", f"{lang}.beta")] == "split_primary" and by_row[("r3", f"{lang}.gamma")] == "split_secondary"
    assert by_row[("r9", None)] == "dropped" and by_row[("r1", f"{lang}.alpha")] == "merged"
    gamma = read_json(out / "points" / f"{lang}.gamma.json")
    assert gamma["aliases"] == ["r4"] and gamma["source_refs"]["r5_split"] == ["r3"] and gamma["source_refs"]["r5"] == ["r4"]
    assert read_json(out / "points" / f"{lang}.beta.json")["aliases"] == ["r3"]
    if lang == "zh":
        assert all("pinyin" in e for e in read_json(out / "points" / "zh.alpha.json")["examples"])
    titles = read_json(out / "functions.json")[0]["title"]
    assert titles == {"vi": "Chức năng thử", "en": "Test function", "zh": "测试功能"}  # zh-Hans -> zh


def test_same_semantic_package_hashes_identically(tmp_path: Path, en_lab: Path) -> None:
    first = do_export(en_lab, out="a")
    second = export_package("en", [f"en.{k}" for k in SHAPE], en_lab, en_lab / "b", set_version="other label",
                            source_commit="f" * 40, source_dirty=True, exported_at="2031-01-01T00:00:00Z")
    assert first.package_hash == second.package_hash  # commit, time, set_version are audit data, outside the hash
    for name in first.points:
        assert (first.out_dir / "points" / f"{name}.json").read_bytes() == (second.out_dir / "points" / f"{name}.json").read_bytes()
    _edit(en_lab, "en", "alpha", lambda p: p["header"].__setitem__("sub", {"vi": "khác", "en": "different"}))
    third = do_export(en_lab, out="c")
    assert third.package_hash != first.package_hash


def test_zip_is_deterministic(en_lab: Path, tmp_path: Path) -> None:
    result = do_export(en_lab)
    one = package_to_zip(result.out_dir, tmp_path / "one.zip").read_bytes()
    two = package_to_zip(result.out_dir, tmp_path / "two.zip").read_bytes()
    assert one == two


def _refused(root: Path, *needles: str, lang: str = "en", **kw: Any) -> list[str]:
    with pytest.raises(ExportError) as caught:
        do_export(root, lang, **kw)
    text = "\n".join(caught.value.problems)
    for needle in needles:
        assert needle in text, text
    assert not (root / "out").exists()  # fail closed: nothing written
    return caught.value.problems


@pytest.mark.parametrize("status", ["draft_ai", "flagged", "auto_ok", "rejected"])
def test_non_approved_points_are_refused(tmp_path: Path, status: str) -> None:
    root = build_lab(tmp_path, "en", status=status)
    _refused(root, "point.not_approved", f"status '{status}'")


def test_one_draft_among_approved_points_refuses_the_whole_export(en_lab: Path) -> None:
    _edit(en_lab, "en", "gamma", lambda p: p.__setitem__("status", "draft_ai"))
    problems = _refused(en_lab, "en.gamma: point.not_approved")
    assert not any(p.startswith("en.alpha") for p in problems)


def test_unresolved_flags_and_missing_review_are_refused(en_lab: Path) -> None:
    _edit(en_lab, "en", "alpha", lambda p: p.__setitem__("flags", ["validate:example.no_target"]))
    _refused(en_lab, "en.alpha: point.flagged")
    _edit(en_lab, "en", "alpha", lambda p: p.update(flags=[], review=None))
    _refused(en_lab, "en.alpha: point.no_review")


def test_placeholder_en_is_refused(en_lab: Path) -> None:
    def copy_vi_into_en(point: dict[str, Any]) -> None:
        point["when_to_use"][0]["en"] = point["when_to_use"][0]["vi"]

    _edit(en_lab, "en", "alpha", copy_vi_into_en)
    text = "\n".join(_refused(en_lab, "locale.en_placeholder", "when_to_use[0]"))
    assert "en.alpha" in text

    # Keep the placeholder detector covered without assuming the committed reference fixture must still contain one.
    fixture = read_json(LAB_ROOT / "fixtures" / "ui" / "en.present_continuous.now.json")
    fixture["when_to_use"][0]["en"] = fixture["when_to_use"][0]["vi"]
    assert any("locale.en_placeholder" in problem for problem in locale_problems(fixture))


def test_missing_required_locale_is_refused(en_lab: Path) -> None:
    def drop_vi(point: dict[str, Any]) -> None:
        del point["examples"][0]["translation"]["vi"]

    _edit(en_lab, "en", "beta", drop_vi)
    _refused(en_lab, "locale.missing vi")
    _edit(en_lab, "en", "beta", lambda p: p["examples"][0]["translation"].update(vi="ok"))
    _edit(en_lab, "en", "beta", lambda p: p["examples"][0]["translation"].pop("en", None))
    _refused(en_lab, "locale.missing en")


def test_function_label_without_real_en_is_refused(en_lab: Path) -> None:
    path = en_lab / "functions" / "functions.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["functions"][0]["title"].pop("en")
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    _refused(en_lab, "function fn.test: title.en missing")


def test_stale_catalogue_is_refused(en_lab: Path) -> None:
    path = en_lab / "inventory" / "canonical_v1" / "en.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["items"][0]["conversion"] = "merge"  # canonical moved; catalog_en.yaml was not regenerated
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    _refused(en_lab, "catalog.stale")


def test_default_safe_metadata_is_refused_with_no_override(en_lab: Path) -> None:
    path = en_lab / "inventory" / "canonical_v1" / "en.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["items"].append({"id": "en.delta", "level": "A1", "title": "Delta", "conversion": "keep", "r5_sources": [], "r5_aliases": []})
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    write_catalog("en", en_lab)
    template = read_json(en_lab / "content" / "en" / "en.alpha.json")
    write_json(en_lab / "content" / "en" / "en.delta.json", {**template, "id": "en.delta", "contrasts": [], "compare": []})
    _refused(en_lab, "en.delta: metadata.default_safe", ids=["en.alpha", "en.delta"])


def test_unresolved_structural_references_are_refused(en_lab: Path) -> None:
    seeds_path = en_lab / "inventory" / "seeds_en.yaml"  # the catalogue, not the draft on disk, decides structure
    seeds = yaml.safe_load(seeds_path.read_text(encoding="utf-8"))
    seeds[0]["prereqs"] = ["en.nowhere"]
    seeds_path.write_text(yaml.safe_dump(seeds, allow_unicode=True), encoding="utf-8")
    write_catalog("en", en_lab)
    _refused(en_lab, "en.nowhere")


def test_a_reference_outside_the_package_resolves_only_to_an_approved_point(en_lab: Path) -> None:
    # export alpha + beta; gamma (approved) is referenced by beta and sits outside: declared external
    ids = ["en.alpha", "en.beta"]
    _, problems = build_r5_map(load_catalog("en", en_lab), ids)
    assert any("r3 also has pieces outside" in p for p in problems)  # the split keeps them together
    _edit(en_lab, "en", "beta", lambda p: p.__setitem__("status", "draft_ai"))
    _refused(en_lab, "en.beta: point.not_approved", ids=["en.beta"])


def test_half_a_split_is_refused_by_the_export(en_lab: Path) -> None:
    _refused(en_lab, "r5_map.incomplete", "r3", ids=["en.alpha", "en.beta"])


def test_duplicate_primary_alias_is_refused_by_the_export(en_lab: Path) -> None:
    path = en_lab / "inventory" / "canonical_v1" / "en.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["items"][2]["r5_aliases"] = ["r3", "r4"]  # gamma also claims r3
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    write_catalog("en", en_lab)
    _refused(en_lab, "r3 is an alias of 2 points")


def test_schema_violations_are_refused(en_lab: Path) -> None:
    _edit(en_lab, "en", "alpha", lambda p: p["header"].__setitem__("invented", "x"))
    # the catalogue-resolved point keeps the extra header key, so the closed profile rejects it
    _refused(en_lab, "profile.schema", "invented")


def test_export_refuses_a_non_empty_output_directory(en_lab: Path) -> None:
    (en_lab / "out").mkdir()
    (en_lab / "out" / "keep.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ExportError, match="not empty"):
        do_export(en_lab)


# --- validate_package catches a tampered package ----------------------------------------------------


def _tamper(out: Path, change: Any, name: str = "en.alpha.json") -> None:
    path = out / "points" / name
    body = read_json(path)
    change(body)
    write_json(path, body)


@pytest.mark.parametrize("change,needle", [
    (lambda b: b.__setitem__("sequence", 99), "content_hash does not match"),
    (lambda b: b.__setitem__("provenance", {"model": "x"}), "profile.schema"),
    (lambda b: b.__setitem__("status", "draft_ai"), "point.not_approved"),
    (lambda b: b.__setitem__("flags", []), "profile.schema"),
    (lambda b: b.__setitem__("target_lang", "zh-Hans"), "profile.schema"),
    (lambda b: b["header"]["title"].pop("en"), "locale.missing en"),
])
def test_validate_package_detects_tampering(en_lab: Path, change: Any, needle: str) -> None:
    out = do_export(en_lab).out_dir
    assert validate_package(out, en_lab) == []
    _tamper(out, change)
    assert any(needle in p for p in validate_package(out, en_lab)), validate_package(out, en_lab)


def test_validate_package_detects_manifest_tampering(en_lab: Path) -> None:
    out = do_export(en_lab).out_dir
    manifest = read_json(out / "package.json")
    for mutate, needle in (
        (lambda m: m["r5_map"].pop(), "package_hash does not match"),
        (lambda m: m["validator"].update(passed=False), "validator.passed"),
        (lambda m: m.update(export_profile="grammar-export-profile/2"), "export_profile"),
        (lambda m: m.update(language="ja"), "language"),
        (lambda m: m["points"].pop(), "file present, not listed"),
    ):
        broken = copy.deepcopy(manifest)
        mutate(broken)
        write_json(out / "package.json", broken)
        assert any(needle in p for p in validate_package(out, en_lab)), needle
    write_json(out / "package.json", {**manifest, "surprise": 1})
    assert "manifest keys differ" in validate_package(out, en_lab)[0]
    write_json(out / "package.json", manifest)
    assert validate_package(out, en_lab) == []


# --- no provider, ever -------------------------------------------------------------------------------


def test_export_makes_zero_provider_calls(en_lab: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def forbidden(name: str) -> Any:
        def _raise(*args: object, **kwargs: object) -> None:
            calls.append(name)
            raise AssertionError(f"{name} must not be called during export")
        return _raise

    monkeypatch.setattr(LLMClient, "__init__", forbidden("LLMClient()"))
    monkeypatch.setattr(LLMClient, "complete", forbidden("LLMClient.complete"))
    monkeypatch.setattr(socket.socket, "connect", forbidden("socket.connect"))
    result = do_export(en_lab)
    assert validate_package(result.out_dir, en_lab) == [] and calls == []


def test_export_modules_do_not_import_any_provider_client() -> None:
    for module in ("export_package", "export_profile", "r5_map"):
        tree = ast.parse((LAB_ROOT / "pipeline" / f"{module}.py").read_text(encoding="utf-8"))
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
            a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        assert not {i for i in imported if any(x in i for x in ("llm_client", "httpx", "anthropic", "openai", "requests"))}, module
    assert export_module.TOOL == "grammar_lab.export_package"


# --- the real repository: the approved corpus can be exported -----------------------------------------


def test_the_real_lab_can_export_an_approved_point(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from grammar_lab.pipeline.cli import app

    out = tmp_path / "pkg"
    result = CliRunner().invoke(app, [
        "export-package", "--lang", "en", "--ids", "en.present_continuous.now", "--out", str(out),
        "--set-version", "t", "--source-commit", "0" * 40, "--allow-dirty",
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    check = CliRunner().invoke(app, ["validate-package", str(out)])
    assert check.exit_code == 0, check.output


def test_cli_exports_and_validates_a_package(en_lab: Path, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from grammar_lab.pipeline.cli import app

    out = tmp_path / "cli_pkg"
    runner = CliRunner()
    built = runner.invoke(app, [
        "export-package", "--lang", "en", "--ids", "en.alpha,en.beta,en.gamma", "--out", str(out), "--set-version", "t",
        "--source-commit", "a" * 40, "--allow-dirty", "--zip", "--root", str(en_lab),
    ])
    assert built.exit_code == 0, built.output
    assert (tmp_path / "cli_pkg.zip").exists()
    assert runner.invoke(app, ["validate-package", str(out), "--root", str(en_lab)]).exit_code == 0
    _tamper(out, lambda b: b.__setitem__("sequence", 42))
    bad = runner.invoke(app, ["validate-package", str(out), "--root", str(en_lab)])
    assert bad.exit_code == 1 and "content_hash" in bad.output
    assert runner.invoke(app, ["export-profile", "--root", str(en_lab)]).exit_code == 0
