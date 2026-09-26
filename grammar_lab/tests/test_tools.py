"""CLI, flag marking, traditional-character detection, formatting and speed."""

from __future__ import annotations

import copy
import json
import time

import pytest
from typer.testing import CliRunner

from grammar_lab.pipeline.cli import app
from grammar_lab.pipeline.jsonio import format_json, read_json
from grammar_lab.pipeline.validate import apply_flags, validate_lang
from grammar_lab.pipeline.zh_script import traditional_chars
from grammar_lab.tests.conftest import Lab

runner = CliRunner()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("我们吃了饭。", []),
        ("乾隆、於是、瞭望、著名", []),  # also valid simplified forms
        ("我們吃了飯。", ["們", "飯"]),
        ("這個這個", ["這", "個"]),
        ("She works in a bank.", []),
    ],
)
def test_traditional_chars(text: str, expected: list[str]) -> None:
    assert traditional_chars(text) == expected


def test_cli_validate_committed_content_exits_zero() -> None:
    result = runner.invoke(app, ["validate", "--lang", "en"])
    assert result.exit_code == 0, result.output
    assert "10 point(s), OK" in result.output


def test_cli_validate_reports_issues_and_exits_one(lab: Lab) -> None:
    lab.points["en.alpha"]["blocks"][3]["text"] = "Changed."
    lab.write()
    result = runner.invoke(app, ["validate", "--lang", "en", "--root", str(lab.root), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert [issue["reason"] for issue in payload["issues"]] == ["validate:example.seg_text_mismatch"]


def test_cli_rejects_unknown_lang() -> None:
    result = runner.invoke(app, ["validate", "--lang", "fr"])
    assert result.exit_code != 0


def test_mark_flags_failing_points_and_clears_after_fix(lab: Lab) -> None:
    good = copy.deepcopy(lab.points["en.alpha"]["blocks"][3])
    lab.points["en.alpha"]["blocks"][3]["seg"] = [["She works in a bank."]]
    lab.write()
    path = lab.content_dir / "en.alpha.json"

    changed = apply_flags(validate_lang("en", lab.root), lab.root)
    point = read_json(path)
    assert changed == ["content/en/en.alpha.json"]
    assert point["status"] == "flagged"
    assert point["flags"] == ["validate:example.no_target"]
    assert apply_flags(validate_lang("en", lab.root), lab.root) == []  # idempotent

    point["blocks"][3] = good
    point["flags"].insert(0, "verify:example_clean")
    path.write_text(format_json(point), encoding="utf-8")
    apply_flags(validate_lang("en", lab.root), lab.root)
    point = read_json(path)
    assert point["flags"] == ["verify:example_clean"]  # other steps' flags survive
    assert point["status"] == "flagged"  # re-routing is route's job
    assert validate_lang("en", lab.root).ok


def test_format_json_round_trips_and_inlines_short_containers() -> None:
    value = {"seg": [["She "], ["works", "target"]], "nested": {"text": "x" * 120}, "empty": []}
    text = format_json(value)
    assert json.loads(text) == value
    assert '"seg": [["She "], ["works", "target"]]' in text
    assert text.endswith("\n")


def test_validate_100_points_under_5_seconds(lab: Lab) -> None:
    base = lab.points["en.alpha"]
    ids = [f"en.p{i:03d}" for i in range(100)]
    lab.points = {}
    for index, point_id in enumerate(ids):
        point = copy.deepcopy(base)
        point["id"] = point_id
        point["prereqs"] = [ids[index - 1]] if index else []
        lab.points[point_id] = point
    lab.functions["functions"][0]["realizations"]["en"] = ids
    lab.write()
    started = time.perf_counter()
    report = validate_lang("en", lab.root)
    elapsed = time.perf_counter() - started
    assert report.ok, report.issues[:5]
    assert report.points == 100
    assert elapsed < 5.0
