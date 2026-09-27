from __future__ import annotations

from pathlib import Path

from grammar_lab.pipeline.report_step import build_report, render_html
from grammar_lab.pipeline.run_context import write_step
from grammar_lab.tests.conftest import Lab


def test_build_report_counts_status_from_current_content(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.points["en.beta"]["status"] = "auto_ok"
    lab.write()
    report = build_report(lab.root, "run1", "en")
    assert report["status_counts"] == {"draft_ai": 1, "auto_ok": 1}


def test_build_report_uses_verify_and_route_step_output(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    write_step(lab.root, "run1", "verify", {
        "points": {
            "en.alpha": {"flags": [{"code": "pitfall_not_caught", "detail": "x"}]},
            "en.beta": {"flags": []},
        }
    })
    write_step(lab.root, "run1", "route", {
        "points": {"en.alpha": {"status": "flagged"}, "en.beta": {"status": "auto_ok"}}
    })
    report = build_report(lab.root, "run1", "en")
    assert report["verify_flag_rate"] == {"pitfall_not_caught": 0.5}
    assert report["route_status_counts"] == {"flagged": 1, "auto_ok": 1}
    assert report["points_checked_by_verify"] == 2


def test_build_report_sums_generate_cost(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    write_step(lab.root, "run1", "generate", {
        "outcomes": [{"point_id": "en.alpha", "cost_usd": 0.01}, {"point_id": "en.beta", "cost_usd": 0.02}]
    })
    report = build_report(lab.root, "run1", "en")
    assert report["api_cost_usd"] == 0.03


def test_build_report_with_no_prior_steps_is_still_valid(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    report = build_report(lab.root, "run-nothing-yet", "en")
    assert report["api_cost_usd"] is None
    assert report["avg_review_seconds"] is None
    assert report["verify_flag_rate"] == {}


def test_build_report_averages_review_seconds_of_reviewed_points(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.points["en.alpha"].update(
        status="approved",
        review={"reviewer": "owner", "reviewed_at": "2026-09-27T00:00:00Z", "seconds": 20},
    )
    lab.points["en.beta"].update(
        status="approved",
        review={"reviewer": "owner", "reviewed_at": "2026-09-27T00:00:00Z", "seconds": 40},
    )
    lab.write()
    report = build_report(lab.root, "run1", "en")
    assert report["avg_review_seconds"] == 30.0


def test_render_html_escapes_and_includes_run_id(tmp_path: Path) -> None:
    lab = Lab(tmp_path, "en")
    lab.write()
    report = build_report(lab.root, "run<1>", "en")
    out = render_html(report)
    assert "run&lt;1&gt;" in out
    assert "<html" in out
