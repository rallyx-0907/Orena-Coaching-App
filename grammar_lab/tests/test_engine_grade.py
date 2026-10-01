"""engine-grade and the blind-solve-off default (human, 2026-09-29, items 3-4)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from grammar_lab.pipeline import engine_grade
from grammar_lab.pipeline.cli import app
from grammar_lab.pipeline.content_store import load_points
from grammar_lab.pipeline.evaluator_client import EvaluatorError, EvaluatorResult
from grammar_lab.pipeline.validate import LAB_ROOT
from grammar_lab.pipeline.verify import _flatten_example_texts, verify_point


class FakeEvaluator:
    """Catches every ``wrong`` under a fixed label, reads everything else clean."""

    def __init__(self, tag: str = "tense") -> None:
        self.calls: list[str] = []
        self._tag = tag

    def evaluate(self, text: str, *, target_cefr: str | None = None) -> EvaluatorResult:
        self.calls.append(text)
        errors = [EvaluatorError(self._tag, text)] if "___" not in text and text.startswith("She reading") else []
        return EvaluatorResult(errors, {})


def _a1_points() -> dict:
    return {pid: p for pid, p in load_points("en", LAB_ROOT).items() if p["level"]["value"] == "A1"}


def test_plan_counts_engine_calls_and_prices_them() -> None:
    points = _a1_points()
    plan = engine_grade.plan(points)
    expected = sum(
        2 * len(p["common_mistakes"]) + sum(len(q["options"]) for q in p["quick_practice"]) for p in points.values()
    )
    assert plan.calls == expected and plan.points == len(points)
    assert plan.cost_usd is not None and 0 < plan.cost_usd < 1.0  # a level is cents, not dollars


def test_grade_point_calls_the_engine_only_for_mistakes_and_quick_practice() -> None:
    point = load_points("en", LAB_ROOT)["en.present_continuous.now"]
    evaluator = FakeEvaluator()
    report = engine_grade.grade_point(point, evaluator=evaluator)  # type: ignore[arg-type]
    assert len(evaluator.calls) == engine_grade.calls_for(point)
    assert report.checked_common_mistakes == len(point["common_mistakes"]) and report.checked_quick_practice == 3


def test_verify_without_a_blind_solver_needs_no_second_model() -> None:
    point = load_points("en", LAB_ROOT)["en.there_is_are"]
    report = verify_point(point, evaluator=FakeEvaluator())  # type: ignore[arg-type]
    assert report.checked_examples == len(_flatten_example_texts(point))
    assert report.checked_quick_practice == len(point["quick_practice"])
    assert not any(flag.code.startswith("blind_solve") for flag in report.flags)


def test_cli_engine_grade_prints_the_estimate_and_stops_without_yes() -> None:
    result = CliRunner().invoke(app, ["engine-grade", "--lang", "en", "--level", "A1", "--evaluator-url", "http://localhost:8020"])
    assert result.exit_code == 0
    assert "engine call(s)" in result.output and "estimated cost" in result.output
    assert "pass --yes to run" in result.output


def test_cli_verify_refuses_a_blind_solver_of_the_family_that_generated(tmp_path: Path) -> None:
    import shutil

    from grammar_lab.pipeline.content_store import load_point, save_point

    for name in ("content", "schema", "functions", "cast"):
        shutil.copytree(LAB_ROOT / name, tmp_path / name)
    point = load_point("en", "en.there_is_are", tmp_path)
    point["provenance"]["model"] = "deepseek:deepseek-flash"
    save_point("en", point, tmp_path)
    result = CliRunner().invoke(app, [
        "verify", "--lang", "en", "--evaluator-url", "http://localhost:8020", "--root", str(tmp_path),
        "--blind-solve", "--blind-provider", "deepseek",
    ])
    assert result.exit_code != 0 and "family" in result.output
