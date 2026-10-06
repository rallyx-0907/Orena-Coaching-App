from __future__ import annotations

from pathlib import Path

from grammar_lab.pipeline.stabilize import (
    acceptance_blockers,
    classify_generation_reason,
    parse_generation_log,
    quality_issues,
)


def _v04_point() -> dict:
    return {
        "schema_version": "0.4",
        "id": "zh.test",
        "provenance": {"model": "deepseek:deepseek-flash"},
        "header": {"summary": {"vi": "Dùng cấu trúc này trong ngữ cảnh phù hợp.", "en": "Use this structure in the matching context."}},
        "when_to_use": [{"vi": "Tình huống 1", "en": "Situation 1"}, {"vi": "Tình huống 2", "en": "Situation 2"}],
        "examples": [
            {"text": "我学习。", "translation": {"vi": "Tôi học.", "en": "I study."}},
            {"text": "他工作。", "translation": {"vi": "Anh ấy làm việc.", "en": "He works."}},
            {"text": "她休息。", "translation": {"vi": "Cô ấy nghỉ.", "en": "She rests."}},
        ],
        "common_mistakes": [{"wrong": "我学习吗。", "right": "我学习。"}],
        "quick_practice": [
            {"q": "我___。"},
            {"q": "他___。"},
            {"q": "她___。"},
        ],
        "personal_production": {"prompt": {"vi": "Viết một câu.", "en": "Write one sentence."}, "sample": {"text": "我学习。"}},
    }


def test_generation_reason_categories_are_stable() -> None:
    assert classify_generation_reason("cache-only mode: no cached completion for deepseek") == "cache_miss"
    assert classify_generation_reason("cached examples require incompatible formula orders") == "formula_order"
    assert classify_generation_reason("slot 2 binding cannot be located in order") == "slot_binding"
    assert classify_generation_reason("two-blank practice item lacks option-to-blank mapping") == "practice_mapping"
    assert classify_generation_reason("question form has no question formula") == "variant_formula"
    assert classify_generation_reason("unexpected semantic conflict") == "semantic_other"


def test_parse_generation_log_collects_every_point_without_stopping() -> None:
    text = """
written              zh.ok                                             cached
a random diagnostic line
error                zh.no_cache                                       n/a  cache-only mode: no cached completion for deepseek:deepseek-flash; provider call blocked
error                zh.bad_formula                                    n/a  cached examples require incompatible formula orders
"""
    outcomes = parse_generation_log(text)
    assert [item["point_id"] for item in outcomes] == ["zh.ok", "zh.no_cache", "zh.bad_formula"]
    assert outcomes[0]["category"] == "written"
    assert outcomes[1]["category"] == "cache_miss"
    assert outcomes[2]["category"] == "formula_order"


def test_quality_gate_accepts_objectively_complete_v04_point() -> None:
    assert quality_issues(_v04_point()) == []


def test_quality_gate_rejects_duplicate_or_incomplete_learning_material() -> None:
    point = _v04_point()
    point["examples"][1]["text"] = point["examples"][0]["text"]
    point["quick_practice"][2]["q"] = point["quick_practice"][0]["q"]
    point["common_mistakes"].append(dict(point["common_mistakes"][0]))
    point["personal_production"] = {}

    codes = {issue["code"] for issue in quality_issues(point)}
    assert "quality.example_duplicate" in codes
    assert "quality.practice_duplicate" in codes
    assert "quality.mistake_duplicate" in codes
    assert "quality.personal_production_missing" in codes


def test_quality_gate_enforces_fixed_v04_generation_cardinality() -> None:
    point = _v04_point()
    point["examples"] = point["examples"][:2]
    point["quick_practice"] = point["quick_practice"][:2]
    codes = {issue["code"] for issue in quality_issues(point)}
    assert "quality.example_count" in codes
    assert "quality.practice_count" in codes


def test_acceptance_requires_complete_clean_corpus() -> None:
    assert acceptance_blockers(
        canonical_total=380,
        generated=380,
        ready=0,
        blocked_metadata=0,
        validator_issues=0,
        quality_issues_count=0,
        deferred=0,
        unresolved_cache_errors=0,
    ) == []

    blockers = acceptance_blockers(
        canonical_total=380,
        generated=379,
        ready=1,
        blocked_metadata=0,
        validator_issues=0,
        quality_issues_count=1,
        deferred=1,
        unresolved_cache_errors=1,
    )
    assert "corpus_incomplete" in blockers
    assert "ready_points" in blockers
    assert "quality_issues" in blockers
    assert "deferred_points" in blockers
    assert "unresolved_cache_errors" in blockers


def test_cli_exposes_one_stabilization_entrypoint() -> None:
    cli = (Path(__file__).resolve().parents[1] / "pipeline" / "cli.py").read_text(encoding="utf-8")
    assert 'from grammar_lab.pipeline.stabilize import' in cli
    assert '@app.command("stabilize-corpus")' in cli
    assert "--skip-cache-sweep" in cli
