"""review-export, feedback parsing / de-duplication / stats, and apply-feedback (human, 2026-09-29, item 4)."""

from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import httpx
import pytest

from grammar_lab.pipeline.apply_feedback import (
    Feedback,
    apply_feedback,
    dedupe,
    feedback_stats,
    parse_files,
)
from grammar_lab.pipeline.content_store import load_point, load_points
from grammar_lab.pipeline.llm_client import LLMClient
from grammar_lab.pipeline.review_export import build_review, write_review
from grammar_lab.pipeline.validate import LAB_ROOT, validate_lang


@pytest.fixture
def lab_copy(tmp_path: Path) -> Path:
    """A private copy of the committed Grammar Lab tree, so feedback can rewrite points."""
    for name in ("content", "schema", "functions", "cast"):
        shutil.copytree(LAB_ROOT / name, tmp_path / name)
    return tmp_path


def _jsonl(path: Path, *rows: dict) -> Path:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return path


def _row(id_: str, block: str, issue: str = "[wording] awkward", severity: str = "major", fix: str = "") -> dict:
    return {"id": id_, "block": block, "issue": issue, "severity": severity, "fix": fix}


# -- export -------------------------------------------------------------------------------------
def test_export_lists_every_point_of_the_level_in_numbered_sections(tmp_path: Path) -> None:
    path = write_review("en", "A1", LAB_ROOT, tmp_path)
    assert path == tmp_path / "en" / "A1.md"
    text = path.read_text(encoding="utf-8")
    for point_id in ("en.articles.a_an", "en.plural_nouns.regular", "en.there_is_are"):
        assert f"### {point_id}" in text
    count = sum(1 for point in load_points("en").values() if point["level"]["value"] == "A1")
    sections = max(1, math.ceil(count / 10))
    assert f"## Phần 1 / {sections}" in text
    assert f"Số điểm: **{count}**" in text and "ký tự" in text
    assert '"id": "...", "block": "..."' in text
    assert "article" in text
    assert "bắt đầu lượt 2" in text and "tiếp tục" in text


def test_export_cuts_a_big_level_into_sections_of_ten(lab_copy: Path) -> None:
    import copy

    source = load_point("en", "en.articles.a_an", lab_copy)
    functions_path = lab_copy / "functions" / "functions.yaml"
    baseline = sum(1 for point in load_points("en", lab_copy).values() if point["level"]["value"] == "A1")
    for index in range(24):
        clone = copy.deepcopy(source)
        clone["id"] = f"en.clone_{index:02d}"
        clone["sequence"] = 10 + index
        (lab_copy / "content" / "en" / f"{clone['id']}.json").write_text(json.dumps(clone), encoding="utf-8")
    assert functions_path.exists()
    text = build_review("en", "A1", lab_copy)
    total = baseline + 24
    sections = math.ceil(total / 10)
    assert f"Số điểm: **{total}**" in text
    assert f"## Phần {sections} / {sections}" in text and f"## Phần {sections + 1}" not in text


def test_zh_export_shows_pinyin_after_each_character(tmp_path: Path) -> None:
    text = write_review("zh", "HSK1", LAB_ROOT, tmp_path).read_text(encoding="utf-8")
    assert "我(wǒ)" in text
    assert "chữ đa âm" in text  # the zh-only review criteria


# -- parse, dedupe, stats -------------------------------------------------------------------------
def test_parse_tolerates_fences_ok_markers_and_reports_bad_lines(tmp_path: Path) -> None:
    file = tmp_path / "a.jsonl"
    file.write_text(
        "```json\n" + json.dumps(_row("en.a", "examples[0]")) + "\n```\n"
        "some chatty sentence\n"
        + json.dumps({"id": "en.a", "block": "none", "issue": "ok", "severity": "none", "fix": ""}) + "\n"
        + json.dumps({"id": "en.a"}) + "\n"
        + json.dumps(_row("en.b", "header", severity="huge")) + "\n",
        encoding="utf-8",
    )
    items, unparsed = parse_files([file])
    assert [(i.id, i.block) for i in items] == [("en.a", "examples[0]")]
    reasons = [u["reason"] for u in unparsed]
    assert "not JSON" in reasons and any("keys" in r for r in reasons) and any("severity" in r for r in reasons)


def test_dedupe_merges_the_same_feedback_from_two_reviewers_and_keeps_the_worst_severity(tmp_path: Path) -> None:
    one = _jsonl(tmp_path / "1.jsonl", _row("en.a", "examples[1]", "[knowledge] has went is wrong", "minor", "has gone"))
    two = _jsonl(tmp_path / "2.jsonl",
                 _row("en.a", "examples[1]", "[knowledge] 'has went' is not English", "blocker", "has gone"),
                 _row("en.a", "examples[2]", "[wording] unnatural", "minor", "say it differently"))
    items, _ = parse_files([one, two])
    kept, merged = dedupe(items)
    assert len(kept) == 2 and len(merged) == 1
    twin = next(k for k in kept if k.block == "examples[1]")
    assert twin.severity == "blocker" and twin.merged == 1 and len(twin.sources) == 2


def test_stats_group_by_issue_type(tmp_path: Path) -> None:
    items = [
        Feedback("en.a", "examples[0]", "[knowledge] x", "major", ""),
        Feedback("en.a", "header", "[scope] y", "minor", ""),
        Feedback("en.b", "examples[1]", "[wording] z", "minor", ""),
        Feedback("en.b", "examples[2]", "no tag", "minor", ""),
    ]
    stats = feedback_stats(items)
    assert stats["by_type"] == {"knowledge": 1, "scope": 1, "wording": 1, "untagged": 1}
    assert stats["by_block"]["examples"] == 3 and stats["total"] == 4


# -- apply ---------------------------------------------------------------------------------------------
def _llm(tmp_path: Path, block: dict, calls: list | None = None) -> LLMClient:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if calls is not None:
            calls.append(body)
        return httpx.Response(200, json={
            "content": [{"type": "tool_use", "name": body["tool_choice"]["name"], "input": {"block": block}}],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })

    return LLMClient("anthropic", "claude-haiku-4-5-20251001", api_key="test", cache_dir=tmp_path / ".cache",
                     transport=httpx.MockTransport(handler))


def test_dry_run_plans_and_skips_what_is_not_the_models_to_fix(lab_copy: Path, tmp_path: Path) -> None:
    file = _jsonl(
        tmp_path / "f.jsonl",
        _row("en.there_is_are", "common_mistakes[0]"),
        _row("LEVEL", "catalogue", "[scope] a point is missing"),
        _row("en.there_is_are", "metadata", "[scope] wrong function"),
        _row("en.nope", "header"),
        _row("en.there_is_are", "bogus[0]"),
    )
    result = apply_feedback("en", "A1", [file], llm=LLMClient("anthropic", "claude-haiku-4-5-20251001"),
                            root=lab_copy, dry_run=True)
    by_status = {o.item.block: o.status for o in result.outcomes}
    assert by_status["common_mistakes[0]"] == "planned"
    assert by_status["catalogue"] == by_status["metadata"] == by_status["bogus[0]"] == "skipped"
    assert result.calls == 1
    assert not (lab_copy / "review").exists()  # a dry run logs nothing


def test_apply_regenerates_the_flagged_block_validates_and_logs(lab_copy: Path, tmp_path: Path) -> None:
    before = load_point("en", "en.there_is_are", lab_copy)
    fixed = dict(before["common_mistakes"][0])
    fixed["reason"] = {"vi": "Lý do đã sửa.", "en": "Fixed reason."}
    block = {
        "wrong": fixed["wrong"], "right": fixed["right"], "reason": fixed["reason"],
        "error_tag": fixed["error_tag"], "l1": fixed["l1"],
    }
    file = _jsonl(tmp_path / "f.jsonl", _row("en.there_is_are", "common_mistakes[0]", "[wording] reason is vague", "major", "clearer"))
    calls: list = []
    result = apply_feedback("en", "A1", [file], llm=_llm(tmp_path, block, calls), root=lab_copy, log_dir=lab_copy / "review")
    assert [o.status for o in result.outcomes] == ["applied"]
    after = load_point("en", "en.there_is_are", lab_copy)
    assert after["common_mistakes"][0]["reason"] == {"vi": "Lý do đã sửa.", "en": "Fixed reason."}
    assert after["common_mistakes"][1:] == before["common_mistakes"][1:]  # nothing else touched
    assert after["status"] == before["status"] != "approved"
    assert after["provenance"]["feedback"][0]["block"] == "common_mistakes[0]"
    assert "reason is vague" in json.dumps(calls[0])  # the model saw the feedback
    assert validate_lang("en", lab_copy).ok
    log = json.loads((lab_copy / "review" / "en" / "A1.applied.json").read_text(encoding="utf-8"))
    assert log["runs"][0]["applied"][0]["block"] == "common_mistakes[0]"


def test_apply_puts_a_block_back_when_the_regeneration_fails_validate(lab_copy: Path, tmp_path: Path) -> None:
    before = load_point("en", "en.there_is_are", lab_copy)
    broken = {**{k: before["common_mistakes"][0][k] for k in ("wrong", "right", "reason", "l1")}, "error_tag": "not_a_tag"}
    file = _jsonl(tmp_path / "f.jsonl", _row("en.there_is_are", "common_mistakes[0]"))
    result = apply_feedback("en", "A1", [file], llm=_llm(tmp_path, broken), root=lab_copy, log_dir=lab_copy / "review")
    assert [o.status for o in result.outcomes] == ["skipped"]
    assert "error_tag" in result.outcomes[0].reason
    assert load_point("en", "en.there_is_are", lab_copy) == before  # restored
    assert validate_lang("en", lab_copy).ok


def test_apply_leaves_an_approved_point_alone_unless_allowed(lab_copy: Path, tmp_path: Path) -> None:
    from grammar_lab.pipeline.content_store import save_point

    point = load_point("en", "en.there_is_are", lab_copy)
    point["status"] = "approved"
    save_point("en", point, lab_copy)
    file = _jsonl(tmp_path / "f.jsonl", _row("en.there_is_are", "common_mistakes[0]"))
    result = apply_feedback("en", "A1", [file], llm=_llm(tmp_path, {}), root=lab_copy, log_dir=lab_copy / "review")
    assert result.outcomes[0].status == "skipped" and "approved" in result.outcomes[0].reason
    assert result.calls == 0
