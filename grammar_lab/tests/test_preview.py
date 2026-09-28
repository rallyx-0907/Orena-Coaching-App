from __future__ import annotations

import json
from pathlib import Path

from grammar_lab.pipeline.preview import build_html, load_preview_data, write_preview
from grammar_lab.tests.conftest import Lab
from grammar_lab.tests.test_validate_rules import _with_v04


def _write_verify(root: Path, run_id: str, lang: str, points: dict) -> None:
    run = root / "reports" / run_id
    run.mkdir(parents=True)
    (run / "verify.json").write_text(json.dumps({"run_id": run_id, "lang": lang, "points": points}), encoding="utf-8")


def _v04_lab(tmp_path: Path) -> Lab:
    lab = Lab(tmp_path, "en")
    _with_v04(lab.points["en.alpha"])
    lab.write()
    return lab


def test_preview_lists_v04_points_and_skips_older_ones(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    data = load_preview_data(lab.root)
    en = data["langs"]["en"]
    assert [entry["point"]["id"] for entry in en["points"]] == ["en.alpha"]
    assert en["skipped"] == ["en.beta"]  # still on schema v0.2


def test_preview_attaches_the_latest_verify_run_for_the_language(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    _write_verify(lab.root, "20260101T000000Z", "en", {"en.alpha": {"flags": [{"code": "old", "detail": ""}]}})
    _write_verify(lab.root, "20260102T000000Z", "en", {"en.alpha": {"flags": []}})
    _write_verify(lab.root, "20260103T000000Z", "zh", {"en.alpha": {"flags": [{"code": "zh", "detail": ""}]}})
    check = load_preview_data(lab.root)["langs"]["en"]["points"][0]["check"]
    assert check["verify"] == {"run_id": "20260102T000000Z", "flags": []}
    assert check["validate"] == []


def test_preview_keeps_a_points_result_when_a_later_run_checked_other_points(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    _write_verify(lab.root, "20260101T000000Z", "en", {"en.alpha": {"flags": [{"code": "x", "detail": ""}]}})
    _write_verify(lab.root, "20260102T000000Z", "en", {"en.beta": {"flags": []}})
    check = load_preview_data(lab.root)["langs"]["en"]["points"][0]["check"]
    assert check["verify"] == {"run_id": "20260101T000000Z", "flags": [{"code": "x", "detail": ""}]}


def test_preview_carries_validate_issues_per_point(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    point = _with_v04(lab.points["en.alpha"])
    point["header"]["level"] = {"framework": "cefr", "value": "A2", "rank": 2}
    lab.write()
    check = load_preview_data(lab.root)["langs"]["en"]["points"][0]["check"]
    assert [issue["code"] for issue in check["validate"]] == ["header.level_mismatch"]
    assert check["verify"] is None


def test_build_html_inlines_data_without_letting_content_close_the_script() -> None:
    html = build_html({"text": "</script><script>alert(1)</script>"}, "<script>__DATA__</script>")
    assert html.count("</script>") == 1
    assert "<\\/script>" in html


def test_write_preview_produces_one_self_contained_file(tmp_path: Path) -> None:
    lab = _v04_lab(tmp_path)
    path = write_preview(lab.root, tmp_path / "out")
    html = path.read_text(encoding="utf-8")
    assert path.name == "index.html"
    assert "__DATA__" not in html
    assert '"en.alpha"' in html
    # Self-contained: nothing loaded from anywhere (the SVG namespace URI is an identifier, not a fetch).
    for external in ("<script src", "<link ", "@import", "url("):
        assert external not in html
